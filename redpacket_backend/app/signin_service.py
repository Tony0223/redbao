"""
每日签到。

规则：
- 周期长度和每天的金币数由 signin_configs 表决定（默认7天一轮，后台可改）
- 连续签到往后推进，断签（昨天没签）从第1天重新开始
- 一天只能签一次，靠 signin_logs 的 (user_id, signin_date) 唯一索引兜底
- 日期按服务器本地时间算
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, models
from app.coin_models import CoinLog, CoinSource, log_coin

DEFAULT_CYCLE = [1100, 1200, 1300, 1400, 1500, 1600, 3000]


class SignInError(Exception):
    """业务错误，message 直接给用户看。"""


def get_cycle(db: Session) -> list:
    """取签到周期配置，没有就按默认值建一份。"""
    configs = (
        db.query(models.SignInConfig)
        .order_by(models.SignInConfig.day_index)
        .all()
    )
    if not configs:
        for i, coins in enumerate(DEFAULT_CYCLE, start=1):
            db.add(models.SignInConfig(day_index=i, coins=coins))
        db.commit()
        configs = (
            db.query(models.SignInConfig)
            .order_by(models.SignInConfig.day_index)
            .all()
        )
    return configs


def _next_day_index(user: models.User, cycle_len: int, today: date) -> int:
    """算今天签到该拿第几天的奖励。"""
    last = user.last_signin_date
    streak = user.signin_streak or 0
    if last is None or last < today - timedelta(days=1):
        return 1                      # 从没签过，或者断签了，从第1天重来
    # 昨天签过，往后推进；满一轮后回到第1天
    return streak % cycle_len + 1


def today_earned_coins(db: Session, user_id: int) -> int:
    """今日已赚：直接查统一流水表，当天所有入账之和。

    原来是手工把"看广告 + 团长返利 + 签到"三张表加起来，
    打卡、福利活动、转盘的金币都漏算了，福利页显示的数字比实际少。
    现在所有发币的地方都往 coin_logs 写，这里查一张表就是全的，
    以后再加玩法也不用回来改这个函数。
    """
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    total = db.query(func.coalesce(func.sum(CoinLog.coins), 0)).filter(
        CoinLog.user_id == user_id,
        CoinLog.coins > 0,
        CoinLog.created_at >= start,
        CoinLog.created_at < end,
    ).scalar() or 0

    return int(total)


def get_info(db: Session, user: models.User) -> dict:
    """签到页信息：周期、每天奖励、已签几天、今天签没签、今日已赚。"""
    cycle = get_cycle(db)
    cycle_len = len(cycle)
    today = date.today()

    today_signed = user.last_signin_date == today
    streak = user.signin_streak or 0
    if not today_signed and user.last_signin_date and user.last_signin_date < today - timedelta(days=1):
        streak = 0   # 断签了，界面上按0显示

    # 本轮内已签几天：满一轮后回到0重新开始
    done_in_cycle = streak % cycle_len
    if today_signed and done_in_cycle == 0 and streak > 0:
        done_in_cycle = cycle_len   # 刚好签满一轮，整轮都点亮

    days = []
    for c in cycle:
        if c.day_index <= done_in_cycle:
            state = "done"
        elif c.day_index == done_in_cycle + 1 and not today_signed:
            state = "today"
        else:
            state = "future"
        days.append({"day": c.day_index, "coins": c.coins, "state": state})

    return {
        "today_earned_coins": today_earned_coins(db, user.id),
        "coins_per_yuan": int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000")),
        "cycle_days": cycle_len,
        "signed_days": streak,
        "today_signed": today_signed,
        "days": days,
    }


def sign_in(db: Session, user: models.User) -> dict:
    """签到发金币。App在激励视频看完之后调这个。"""
    cycle = get_cycle(db)
    cycle_len = len(cycle)
    today = date.today()

    # 锁住用户这一行，防止连点重复签到
    locked = (
        db.query(models.User)
        .filter(models.User.id == user.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if locked.last_signin_date == today:
        raise SignInError("今天已经签到过了，明天再来")

    day_index = _next_day_index(locked, cycle_len, today)
    coins = next((c.coins for c in cycle if c.day_index == day_index), 0)

    # 断签或满一轮后，连续天数从1重新算
    if day_index == 1:
        new_streak = 1
    else:
        new_streak = (locked.signin_streak or 0) + 1

    locked.coin_balance += coins
    locked.signin_streak = new_streak
    locked.last_signin_date = today
    db.add(locked)
    db.add(models.SignInLog(
        user_id=locked.id,
        signin_date=today,
        day_index=day_index,
        coins=coins,
    ))
    log_coin(
        db, locked.id, CoinSource.SIGNIN, coins,
        remark=f"第{day_index}天签到", balance_after=locked.coin_balance,
    )

    try:
        db.commit()
    except IntegrityError:
        # 并发情况下唯一索引挡下来了，说明这一天已经签过
        db.rollback()
        raise SignInError("今天已经签到过了，明天再来")

    db.refresh(locked)
    return {
        "coins": coins,
        "day_index": day_index,
        "signed_days": new_streak,
        "balance": locked.coin_balance,
    }
