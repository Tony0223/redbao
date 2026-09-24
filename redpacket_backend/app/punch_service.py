"""
每日打卡·爆金币。

流程：
- 每天 punch_start_time ~ punch_end_time 之间可以打卡（默认7:00-11:00）
- 用户看完激励视频才算打卡成功，按先后顺序记名次
- 奖金池 = 后台配的固定底池 + 每人打卡时注入的金币（注入是[inject_min, inject_max]随机）
- 每天 punch_publish_time（默认11:10）统一开奖：前120名按四档瓜分，档内按活跃权重（累计看广告次数）分配
- 121名之后不参与分配
"""
import logging
import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, models
from app.coin_models import CoinSource, log_coin

logger = logging.getLogger("punch")

# 四档：(名次上限, 占总奖池比例)
TIERS = [(10, 0.20), (25, 0.15), (50, 0.10), (120, 0.55)]
MAX_RANK = TIERS[-1][0]

DEFAULT_RULES = """早起打卡分红规则

一、打卡时间
每日 7:00-11:00 完成签到打卡，逾期视为当日未参与。

二、分红总分配
当日打卡奖金池 100% 分给打卡用户。

三、用户分红分配比例（按用户活跃权重随机分配）
前 120 名用户可分得 100% 奖金池，再按排名分成四档：
1. 前 10 名：分得总奖金的 20%
2. 第 11-25 名：分得总奖金的 15%
3. 第 26-50 名：分得总奖金的 10%
4. 第 51-120 名：分得总奖金的 55%

四、结果公布
每日 11:10 后统一公布打卡排名与奖励结果。"""


class PunchError(Exception):
    """业务错误，message 直接给用户看。"""


def _parse_time(value: str, default: time) -> time:
    try:
        h, m, s = value.strip().split(":")
        return time(int(h), int(m), int(s))
    except (ValueError, AttributeError):
        return default


def get_settings(db: Session) -> dict:
    return {
        "enabled": crud.get_setting(db, "punch_enabled", "true").strip().lower() == "true",
        "start": _parse_time(crud.get_setting(db, "punch_start_time", "07:00:00"), time(7, 0, 0)),
        "end": _parse_time(crud.get_setting(db, "punch_end_time", "11:00:00"), time(11, 0, 0)),
        "publish": _parse_time(crud.get_setting(db, "punch_publish_time", "11:10:00"), time(11, 10, 0)),
        "base_pool": int(crud.get_setting(db, "punch_base_pool", "0") or 0),
        "inject_min": int(crud.get_setting(db, "punch_inject_min", "0") or 0),
        "inject_max": int(crud.get_setting(db, "punch_inject_max", "0") or 0),
        "rules": crud.get_setting(db, "punch_rules", "").strip() or DEFAULT_RULES,
    }


def get_or_create_pool(db: Session, day: date, base_pool: int) -> models.PunchPool:
    pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == day).first()
    if pool is None:
        pool = models.PunchPool(punch_date=day, base_coins=base_pool)
        db.add(pool)
        try:
            db.commit()
        except IntegrityError:
            # 并发下别的请求先建了，用它的
            db.rollback()
            pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == day).first()
        else:
            db.refresh(pool)
    return pool


def get_info(db: Session, user: models.User) -> dict:
    s = get_settings(db)
    now = datetime.now()
    today = now.date()

    pool = get_or_create_pool(db, today, s["base_pool"])
    my_log = (
        db.query(models.PunchLog)
        .filter(models.PunchLog.user_id == user.id, models.PunchLog.punch_date == today)
        .first()
    )

    if not s["enabled"]:
        status = "closed"
    elif my_log is not None:
        status = "done"
    elif now.time() < s["start"]:
        status = "before"
    elif now.time() > s["end"]:
        status = "closed"
    else:
        status = "open"

    return {
        "status": status,
        "start_time": s["start"].strftime("%H:%M:%S"),
        "end_time": s["end"].strftime("%H:%M:%S"),
        "publish_time": s["publish"].strftime("%H:%M:%S"),
        "server_now_ms": int(now.timestamp() * 1000),
        "pool_coins": pool.base_coins + pool.injected_coins,
        "punch_count": pool.punch_count,
        "my_rank": my_log.rank_no if my_log else 0,
        "my_reward_coins": my_log.reward_coins if my_log else 0,
        "published": pool.published,
        "rules": s["rules"],
    }


def punch(db: Session, user: models.User) -> dict:
    """打卡。App在激励视频看完之后调这个。

    注意：打卡这一步不发金币，只记名次，金币等 11:10 开奖时统一发，
    所以这里没有 coin_logs 记录，流水在 publish() 里写。
    """
    s = get_settings(db)
    if not s["enabled"]:
        raise PunchError("打卡活动暂未开启")

    now = datetime.now()
    today = now.date()
    if now.time() < s["start"]:
        raise PunchError(f"还没到打卡时间，每天 {s['start'].strftime('%H:%M')} 开始")
    if now.time() > s["end"]:
        raise PunchError("今日打卡已结束，明天早点来")

    exists = (
        db.query(models.PunchLog.id)
        .filter(models.PunchLog.user_id == user.id, models.PunchLog.punch_date == today)
        .first()
    )
    if exists:
        raise PunchError("今天已经打过卡了")

    pool = get_or_create_pool(db, today, s["base_pool"])

    # 锁住奖池这一行来排队，保证名次不重复
    locked_pool = (
        db.query(models.PunchPool)
        .filter(models.PunchPool.id == pool.id)
        .with_for_update()
        .populate_existing()
        .first()
    )

    inject = 0
    if s["inject_max"] > 0:
        low = min(s["inject_min"], s["inject_max"])
        inject = random.randint(low, s["inject_max"])

    rank_no = locked_pool.punch_count + 1
    locked_pool.punch_count = rank_no
    locked_pool.injected_coins += inject
    if locked_pool.base_coins != s["base_pool"]:
        locked_pool.base_coins = s["base_pool"]   # 后台中途改了底池，跟着更新
    db.add(locked_pool)

    db.add(models.PunchLog(
        user_id=user.id,
        punch_date=today,
        rank_no=rank_no,
        weight=user.ad_watch_count or 0,
        injected_coins=inject,
    ))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PunchError("今天已经打过卡了")

    db.refresh(locked_pool)
    return {
        "rank": rank_no,
        "pool_coins": locked_pool.base_coins + locked_pool.injected_coins,
        "punch_count": locked_pool.punch_count,
    }


def get_rank(db: Session, user: models.User, day: date = None, limit: int = 120) -> dict:
    day = day or date.today()
    pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == day).first()

    rows = (
        db.query(models.PunchLog, models.User)
        .outerjoin(models.User, models.User.id == models.PunchLog.user_id)
        .filter(models.PunchLog.punch_date == day)
        .order_by(models.PunchLog.rank_no)
        .limit(limit)
        .all()
    )

    items = []
    my_rank = 0
    for log, u in rows:
        is_me = log.user_id == user.id
        if is_me:
            my_rank = log.rank_no
        items.append({
            "rank": log.rank_no,
            "nickname": (u.nickname if u and u.nickname else f"用户{log.user_id}"),
            "reward_coins": log.reward_coins,
            "is_me": is_me,
        })

    if my_rank == 0:
        mine = (
            db.query(models.PunchLog)
            .filter(models.PunchLog.user_id == user.id, models.PunchLog.punch_date == day)
            .first()
        )
        my_rank = mine.rank_no if mine else 0

    return {
        "date": day.strftime("%Y-%m-%d"),
        "published": bool(pool and pool.published),
        "pool_coins": (pool.base_coins + pool.injected_coins) if pool else 0,
        "punch_count": pool.punch_count if pool else 0,
        "my_rank": my_rank,
        "list": items,
    }


# ====================== 开奖 ======================

def _split_by_weight(logs: list, total: int) -> dict:
    """
    档内按权重分配。权重全为0就平均分。
    返回 {punch_log_id: coins}，余数给权重最高的那个。
    """
    result = {}
    if not logs or total <= 0:
        return {log.id: 0 for log in logs}

    weights = [max(0, log.weight or 0) for log in logs]
    weight_sum = sum(weights)

    if weight_sum == 0:
        each = total // len(logs)
        for log in logs:
            result[log.id] = each
        remain = total - each * len(logs)
        if remain > 0:
            result[logs[0].id] += remain
        return result

    allocated = 0
    for log, w in zip(logs, weights):
        coins = total * w // weight_sum
        result[log.id] = coins
        allocated += coins

    # 除不尽的余数给权重最高的
    remain = total - allocated
    if remain > 0:
        top = max(zip(logs, weights), key=lambda x: x[1])[0]
        result[top.id] += remain
    return result


def publish(db: Session, day: date = None, force: bool = False) -> dict:
    """
    开奖：按名次分档、档内按权重分配、给用户加金币。
    幂等——已开奖的日期不会重复发放（除非 force=True 且还没发过）。
    """
    day = day or date.today()
    pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == day).first()
    if pool is None:
        return {"ok": False, "message": f"{day} 没有打卡数据"}
    if pool.published and not force:
        return {"ok": False, "message": f"{day} 已经开过奖了"}

    total = pool.base_coins + pool.injected_coins
    logs = (
        db.query(models.PunchLog)
        .filter(models.PunchLog.punch_date == day, models.PunchLog.rank_no <= MAX_RANK)
        .order_by(models.PunchLog.rank_no)
        .all()
    )

    if not logs or total <= 0:
        pool.published = True
        pool.published_at = datetime.now()
        db.add(pool)
        db.commit()
        return {"ok": True, "message": f"{day} 无人打卡或奖池为空，直接标记已开奖",
                "total": total, "winners": 0}

    # 按四档切分
    groups = []
    prev = 0
    for upper, ratio in TIERS:
        members = [log for log in logs if prev < log.rank_no <= upper]
        groups.append({"ratio": ratio, "members": members})
        prev = upper

    # 空档的比例匀给有人的档，避免奖池浪费
    active_ratio = sum(g["ratio"] for g in groups if g["members"])
    if active_ratio <= 0:
        active_ratio = 1

    rewards = {}
    allocated = 0
    for g in groups:
        if not g["members"]:
            continue
        group_total = int(total * g["ratio"] / active_ratio)
        part = _split_by_weight(g["members"], group_total)
        rewards.update(part)
        allocated += sum(part.values())

    # 分配余数给第1名
    remain = total - allocated
    if remain > 0 and logs:
        rewards[logs[0].id] = rewards.get(logs[0].id, 0) + remain

    # 发金币
    winners = 0
    for log in logs:
        coins = rewards.get(log.id, 0)
        if coins <= 0 or log.rewarded:
            continue
        user = crud.get_user_by_id(db, log.user_id)
        if user is None:
            continue
        user.coin_balance += coins
        db.add(user)
        log_coin(
            db, user.id, CoinSource.PUNCH, coins,
            remark=f"第{log.rank_no}名", balance_after=user.coin_balance,
        )
        log.reward_coins = coins
        log.rewarded = True
        db.add(log)
        winners += 1

    pool.published = True
    pool.published_at = datetime.now()
    db.add(pool)
    db.commit()

    logger.info("打卡开奖 %s：奖池 %s 金币，%s 人中奖", day, total, winners)
    return {"ok": True, "message": f"{day} 开奖完成",
            "total": total, "winners": winners}


def publish_if_due(db: Session) -> None:
    """
    定时任务调这个：到了公布时间就给今天开奖。
    已开奖的会被 publish() 挡掉，重复调用没有副作用。
    """
    s = get_settings(db)
    if not s["enabled"]:
        return
    now = datetime.now()
    if now.time() < s["publish"]:
        return
    pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == now.date()).first()
    if pool is None or pool.published:
        return
    publish(db, now.date())
