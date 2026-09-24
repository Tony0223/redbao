"""福利活动：今日看满 N 次广告 → 自动发 M 金币。

v2：身份改为走 token（Authorization: Bearer xxx），跟 /api/welfare/*、/api/punch 等接口一致。
    客户端不再传 user_id。

对外接口：
    GET  /api/bonus/info      取配置 + 我的今日进度
    POST /api/bonus/watch     看完一次激励视频后上报，满N次自动发币

后台页面在 app/routers/admin_bonus.py，走项目统一的 render_page 导航和 verify_admin 鉴权。
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bonus_models import BonusActivityConfig, BonusActivityProgress
from app.coin_models import CoinSource, log_coin
from app.database import get_db
from app.models import User

# ===== 登录依赖：用你项目里现成的那个，按常见位置依次尝试导入 =====
# 如果三个都不对，把下面这一段整体换成一行：from app.你的文件 import get_current_user
try:
    from app.dependencies import get_current_user  # type: ignore
except ImportError:
    try:
        from app.auth import get_current_user  # type: ignore
    except ImportError:
        try:
            from app.deps import get_current_user  # type: ignore
        except ImportError:
            try:
                from app.routers.user import get_current_user  # type: ignore
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "福利活动模块找不到登录依赖 get_current_user，"
                    "把 app/routers/bonus.py 顶部这一段换成你项目里实际的那一行"
                ) from exc

router = APIRouter(tags=["福利活动"])

# ===== 唯一一处跟现有 models.py 的字段耦合：用户金币余额字段名 =====
COIN_FIELD = "coin_balance"

DEFAULT_TIPS = (
    "注意：如果有用户在当日浏览完广告没有金币获得，说明你创造的广告价值非常低，\n"
    "大家可以通过学习提升权重，可在教学视频中学习"
)


def _current_user_id(current_user) -> int:
    """兼容依赖返回 User 对象 / dict / 纯 id 三种写法"""
    if isinstance(current_user, int):
        return current_user
    if isinstance(current_user, dict):
        uid = current_user.get("id") or current_user.get("user_id")
        if uid is None:
            raise HTTPException(status_code=401, detail="登录状态异常，请重新登录")
        return int(uid)
    uid = getattr(current_user, "id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="登录状态异常，请重新登录")
    return int(uid)


def _add_coins(user: User, amount: int) -> int:
    current = getattr(user, COIN_FIELD) or 0
    new_balance = current + amount
    setattr(user, COIN_FIELD, new_balance)
    return new_balance


def get_config(db: Session) -> BonusActivityConfig:
    """取配置，没有就建一行默认值"""
    cfg = db.query(BonusActivityConfig).first()
    if cfg is None:
        cfg = BonusActivityConfig(
            id=1,
            is_enabled=True,
            target_count=20,
            reward_coin=20000,
            min_interval_seconds=10,
            tips_text=DEFAULT_TIPS,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _get_or_create_progress(
    db: Session, user_id: int, today: date, for_update: bool = False
) -> BonusActivityProgress:
    q = db.query(BonusActivityProgress).filter(
        BonusActivityProgress.user_id == user_id,
        BonusActivityProgress.stat_date == today,
    )
    if for_update:
        # 行锁，防止连点造成重复计数/重复发币
        try:
            q = q.with_for_update()
        except Exception:
            pass
    row = q.first()
    if row is not None:
        return row

    row = BonusActivityProgress(
        user_id=user_id, stat_date=today, watch_count=0, is_claimed=False, reward_coin=0
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # 并发时另一个请求先插进去了
        db.rollback()
        row = (
            db.query(BonusActivityProgress)
            .filter(
                BonusActivityProgress.user_id == user_id,
                BonusActivityProgress.stat_date == today,
            )
            .first()
        )
    else:
        db.refresh(row)
    return row


def _info_payload(cfg: BonusActivityConfig, row) -> dict:
    watch_count = row.watch_count if row else 0
    completed = bool(row.is_claimed) if row else False
    target = cfg.target_count
    return {
        "enabled": bool(cfg.is_enabled),
        "title": f"看满{target}次视频 · 领{cfg.reward_coin}金币",
        "subtitle": "进度实时保存 · 看完即计数",
        "target_count": target,
        "reward_coin": cfg.reward_coin,
        "watch_count": min(watch_count, target),
        "completed": completed,
        "tips_text": cfg.tips_text or DEFAULT_TIPS,
    }


# ==================== App 接口 ====================


@router.get("/api/bonus/info")
def bonus_info(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """进入福利活动页时调用，拿配置和今日进度"""
    user_id = _current_user_id(current_user)
    cfg = get_config(db)
    row = (
        db.query(BonusActivityProgress)
        .filter(
            BonusActivityProgress.user_id == user_id,
            BonusActivityProgress.stat_date == date.today(),
        )
        .first()
    )
    return _info_payload(cfg, row)


@router.post("/api/bonus/watch")
def bonus_watch(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """看完一个激励视频后上报一次，满 N 次当场发币"""
    user_id = _current_user_id(current_user)
    cfg = get_config(db)
    if not cfg.is_enabled:
        raise HTTPException(status_code=400, detail="福利活动未开启")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    today = date.today()
    row = _get_or_create_progress(db, user_id, today, for_update=True)

    # 今日已完成，不再计数
    if row.is_claimed:
        payload = _info_payload(cfg, row)
        payload.update(
            {"ok": True, "just_rewarded": False, "reward_got": 0,
             "message": "今日任务已完成，明天再来"}
        )
        return payload

    # 防刷：两次上报间隔过短直接忽略
    now = datetime.now()
    if (
        cfg.min_interval_seconds
        and row.last_watch_at
        and (now - row.last_watch_at).total_seconds() < cfg.min_interval_seconds
    ):
        payload = _info_payload(cfg, row)
        payload.update(
            {"ok": False, "just_rewarded": False, "reward_got": 0,
             "message": "操作太快了，请稍后再试"}
        )
        return payload

    row.watch_count = (row.watch_count or 0) + 1
    row.last_watch_at = now

    just_rewarded = False
    balance = None
    if row.watch_count >= cfg.target_count:
        _add_coins(user, cfg.reward_coin)
        balance = getattr(user, COIN_FIELD)
        log_coin(db, user_id, CoinSource.BONUS, cfg.reward_coin,
                 remark=f"看满{cfg.target_count}次视频", balance_after=balance)
        row.is_claimed = True
        row.reward_coin = cfg.reward_coin
        row.claimed_at = now
        just_rewarded = True

    db.commit()
    db.refresh(row)

    payload = _info_payload(cfg, row)
    payload.update(
        {
            "ok": True,
            "just_rewarded": just_rewarded,
            "reward_got": cfg.reward_coin if just_rewarded else 0,
            "coin_balance": balance,
            "message": f"恭喜获得{cfg.reward_coin}金币"
            if just_rewarded
            else f"进度 {payload['watch_count']}/{payload['target_count']}",
        }
    )
    return payload
