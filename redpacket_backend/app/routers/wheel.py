"""幸运转盘。

规则要点：
- 抽奖结果由服务端决定，客户端只负责把转盘转到对应格子，防止本地改结果
- 流程是【先看完激励视频 → 再调 /draw】：广告在抽奖之前，所以 /draw 一次性
  扣次数、定奖品、发金币，记录直接落成 claimed，不再需要二次领取
- /claim 保留，只用于补发历史遗留的 pending 记录（老版本流程留下的）
- 中奖概率用整数权重，另支持每日全局限量、每人每日限次

对外接口：
    GET  /api/wheel/info          转盘配置、格子、我的剩余次数、遗留待领取记录
    POST /api/wheel/ad_chance     看完激励视频换 1 次抽奖机会（新流程下一般用不到）
    POST /api/wheel/draw          抽奖：看完广告后调用，扣次数、定结果、当场发金币
    POST /api/wheel/claim         补发历史遗留的待领取记录
    GET  /api/wheel/records       我的抽奖记录（分页）

后台页面在 app/routers/admin_wheel.py，走项目统一的 render_page 导航和 verify_admin 鉴权。
"""
import random
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.coin_models import CoinSource, log_coin
from app.database import get_db
from app.models import User
from app.wheel_models import WheelChance, WheelConfig, WheelDrawRecord, WheelPrize

# ===== 登录依赖：跟其他接口一致，身份由 token 决定 =====
# 如果三个位置都不对，把这一段换成一行：from app.你的文件 import get_current_user
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
                    "幸运转盘模块找不到登录依赖 get_current_user，"
                    "把 app/routers/wheel.py 顶部这一段换成你项目里实际的那一行"
                ) from exc

router = APIRouter(tags=["幸运转盘"])

# 用户金币余额字段名，跟 bonus.py 保持一致
COIN_FIELD = "coin_balance"

DEFAULT_RULES = (
    "1. 参与对象：全体符合活动条件的用户。\n"
    "2. 抽奖次数：每人每日可抽取的次数有限，次数当日清零不累计。\n"
    "3. 奖品设置：随机抽取对应奖品金币，限量奖品先抽先得。\n"
    "4. 领奖方式：每次抽奖前需完整观看视频，看完即可转动转盘，奖品金币即时到账。\n"
    "5. 严禁违规刷奖、作弊行为，违规将取消中奖资格并封禁参与权限。\n"
    "活动最终解释权归主办方所有。"
)

# 没配奖品时自动写入的默认6个格子（照截图）
DEFAULT_PRIZES = [
    # label,          min,    max,    weight, daily_limit, user_daily_limit
    ("66666", 66666, 66666, 1, 3, 1),
    ("9999-18888", 9999, 18888, 30, 0, 0),
    ("16666-38888", 16666, 38888, 8, 0, 0),
    ("18888", 18888, 18888, 15, 0, 0),
    ("26666", 26666, 26666, 6, 0, 0),
    ("33333", 33333, 33333, 3, 10, 1),
]


def _current_user_id(current_user) -> int:
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


# ==================== 配置与奖品 ====================


def get_config(db: Session) -> WheelConfig:
    cfg = db.query(WheelConfig).first()
    if cfg is None:
        cfg = WheelConfig(
            id=1,
            is_enabled=True,
            daily_free_chances=10,
            ad_chance_enabled=False,
            ad_chance_max=0,
            min_interval_seconds=3,
            rules_text=DEFAULT_RULES,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def get_prizes(db: Session, only_enabled: bool = True):
    """转盘格子，按 sort_order 排序；列表下标就是客户端的格子序号"""
    q = db.query(WheelPrize)
    if only_enabled:
        q = q.filter(WheelPrize.is_enabled == True)  # noqa: E712
    prizes = q.order_by(WheelPrize.sort_order.asc(), WheelPrize.id.asc()).all()

    if not prizes and only_enabled and db.query(WheelPrize).count() == 0:
        # 一个奖品都没配，先写一套默认的，省得后台是空页面
        for i, (label, mn, mx, w, dl, udl) in enumerate(DEFAULT_PRIZES):
            db.add(
                WheelPrize(
                    label=label, min_coin=mn, max_coin=mx, weight=w,
                    daily_limit=dl, user_daily_limit=udl, sort_order=i, is_enabled=True,
                )
            )
        db.commit()
        prizes = (
            db.query(WheelPrize)
            .filter(WheelPrize.is_enabled == True)  # noqa: E712
            .order_by(WheelPrize.sort_order.asc(), WheelPrize.id.asc())
            .all()
        )
    return prizes


def _taken_today(db: Session, today: date, user_id: int = None):
    """今天各奖品已被抽走的次数（pending 也算占用，避免超发）"""
    q = db.query(WheelDrawRecord.prize_id, func.count(WheelDrawRecord.id)).filter(
        WheelDrawRecord.stat_date == today,
        WheelDrawRecord.status.in_(["pending", "claimed"]),
    )
    if user_id is not None:
        q = q.filter(WheelDrawRecord.user_id == user_id)
    return {pid: cnt for pid, cnt in q.group_by(WheelDrawRecord.prize_id).all()}


def _available_prizes(db: Session, prizes, today: date, user_id: int):
    """按限量和每人限次过滤出当前还能中的奖品"""
    global_taken = _taken_today(db, today)
    user_taken = _taken_today(db, today, user_id)
    out = []
    for p in prizes:
        if p.weight <= 0:
            continue
        if p.daily_limit and global_taken.get(p.id, 0) >= p.daily_limit:
            continue
        if p.user_daily_limit and user_taken.get(p.id, 0) >= p.user_daily_limit:
            continue
        out.append(p)
    return out


def _pick_prize(candidates):
    """按权重随机挑一个"""
    total = sum(p.weight for p in candidates)
    r = random.randint(1, total)
    acc = 0
    for p in candidates:
        acc += p.weight
        if r <= acc:
            return p
    return candidates[-1]


# ==================== 次数账本 ====================


def _get_or_create_chance(db: Session, user_id: int, today: date, for_update: bool = False):
    q = db.query(WheelChance).filter(
        WheelChance.user_id == user_id, WheelChance.stat_date == today
    )
    if for_update:
        try:
            q = q.with_for_update()
        except Exception:
            pass
    row = q.first()
    if row is not None:
        return row

    row = WheelChance(user_id=user_id, stat_date=today, used_chances=0, ad_chances_got=0)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = (
            db.query(WheelChance)
            .filter(WheelChance.user_id == user_id, WheelChance.stat_date == today)
            .first()
        )
    else:
        db.refresh(row)
    return row


def _chances_left(cfg: WheelConfig, row: WheelChance) -> int:
    total = cfg.daily_free_chances + (row.ad_chances_got if row else 0)
    used = row.used_chances if row else 0
    return max(0, total - used)


def _ad_chance_left(cfg: WheelConfig, row: WheelChance) -> int:
    if not cfg.ad_chance_enabled:
        return 0
    got = row.ad_chances_got if row else 0
    return max(0, cfg.ad_chance_max - got)


# ==================== App 接口 ====================


@router.get("/api/wheel/info")
def wheel_info(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user_id = _current_user_id(current_user)
    today = date.today()
    cfg = get_config(db)
    prizes = get_prizes(db)
    row = (
        db.query(WheelChance)
        .filter(WheelChance.user_id == user_id, WheelChance.stat_date == today)
        .first()
    )

    pending = (
        db.query(WheelDrawRecord)
        .filter(
            WheelDrawRecord.user_id == user_id,
            WheelDrawRecord.stat_date == today,
            WheelDrawRecord.status == "pending",
        )
        .order_by(WheelDrawRecord.id.desc())
        .first()
    )
    prize_index = {p.id: i for i, p in enumerate(prizes)}

    return {
        "enabled": bool(cfg.is_enabled),
        "rules_text": cfg.rules_text or DEFAULT_RULES,
        "chances_left": _chances_left(cfg, row),
        "ad_chance_enabled": bool(cfg.ad_chance_enabled),
        "ad_chance_left": _ad_chance_left(cfg, row),
        "prizes": [
            {
                "index": i,
                "label": p.label,
                "min_coin": p.min_coin,
                "max_coin": p.max_coin,
            }
            for i, p in enumerate(prizes)
        ],
        "pending": (
            {
                "record_id": pending.id,
                "prize_index": prize_index.get(pending.prize_id, 0),
                "label": pending.prize_label,
                "coin": pending.coin,
            }
            if pending
            else None
        ),
    }


@router.post("/api/wheel/ad_chance")
def wheel_ad_chance(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """看完一个激励视频，换 1 次抽奖机会"""
    user_id = _current_user_id(current_user)
    cfg = get_config(db)
    if not cfg.is_enabled:
        raise HTTPException(status_code=400, detail="活动未开启")
    if not cfg.ad_chance_enabled:
        raise HTTPException(status_code=400, detail="今日次数已用完，明天再来")

    today = date.today()
    row = _get_or_create_chance(db, user_id, today, for_update=True)
    if row.ad_chances_got >= cfg.ad_chance_max:
        raise HTTPException(status_code=400, detail="今天换取次数已达上限，明天再来")

    row.ad_chances_got = (row.ad_chances_got or 0) + 1
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "chances_left": _chances_left(cfg, row),
        "ad_chance_left": _ad_chance_left(cfg, row),
        "message": "获得1次抽奖机会",
    }


@router.post("/api/wheel/draw")
def wheel_draw(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """抽奖。客户端必须在激励视频【完整看完】之后才调用这个接口。

    广告已经在前面看过了，所以这里一次性把事做完：扣次数、定奖品、发金币。
    """
    user_id = _current_user_id(current_user)
    cfg = get_config(db)
    if not cfg.is_enabled:
        raise HTTPException(status_code=400, detail="活动未开启")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    today = date.today()
    prizes = get_prizes(db)
    if not prizes:
        raise HTTPException(status_code=400, detail="奖品配置为空，请稍后再试")

    row = _get_or_create_chance(db, user_id, today, for_update=True)

    if _chances_left(cfg, row) <= 0:
        raise HTTPException(status_code=400, detail="今日抽奖次数已用完")

    now = datetime.now()
    if (
        cfg.min_interval_seconds
        and row.last_draw_at
        and (now - row.last_draw_at).total_seconds() < cfg.min_interval_seconds
    ):
        raise HTTPException(status_code=400, detail="手速太快了，稍等一下再抽")

    # 先看还有没有能中的奖品，没有就不扣次数
    candidates = _available_prizes(db, prizes, today, user_id)
    if not candidates:
        raise HTTPException(status_code=400, detail="今日奖品已抽完，明天再来")

    prize = _pick_prize(candidates)
    low, high = min(prize.min_coin, prize.max_coin), max(prize.min_coin, prize.max_coin)
    coin = random.randint(low, high) if high > low else low

    # 广告已看完，金币当场到账，记录直接落成已领取
    balance = _add_coins(user, coin)
    log_coin(db, user_id, CoinSource.WHEEL, coin,
             remark=f"抽中{prize.label}", balance_after=balance)
    record = WheelDrawRecord(
        user_id=user_id,
        stat_date=today,
        prize_id=prize.id,
        prize_label=prize.label,
        coin=coin,
        status="claimed",
        created_at=now,
        claimed_at=now,
    )
    db.add(record)

    row.used_chances = (row.used_chances or 0) + 1
    row.last_draw_at = now
    db.commit()
    db.refresh(record)
    db.refresh(row)

    prize_index = {p.id: i for i, p in enumerate(prizes)}
    return {
        "ok": True,
        "record_id": record.id,
        "prize_index": prize_index.get(prize.id, 0),
        "label": prize.label,
        "coin": coin,
        "coin_balance": balance,
        "need_ad": False,
        "chances_left": _chances_left(cfg, row),
        "ad_chance_left": _ad_chance_left(cfg, row),
        "message": f"恭喜获得{coin}金币",
    }


class ClaimRequest(BaseModel):
    record_id: int


@router.post("/api/wheel/claim")
def wheel_claim(
    req: ClaimRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """补发待领取记录。

    新流程（先看广告再抽奖）下 /draw 已经当场发币，不会再产生 pending 记录，
    这个接口只用于补发老版本流程遗留的那些。
    """
    user_id = _current_user_id(current_user)
    cfg = get_config(db)

    q = db.query(WheelDrawRecord).filter(
        WheelDrawRecord.id == req.record_id, WheelDrawRecord.user_id == user_id
    )
    try:
        q = q.with_for_update()
    except Exception:
        pass
    record = q.first()

    if record is None:
        raise HTTPException(status_code=404, detail="抽奖记录不存在")
    if record.status == "claimed":
        raise HTTPException(status_code=400, detail="该奖励已经领取过了")
    if record.status == "expired" or record.stat_date != date.today():
        record.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="奖励已过期，当日中奖需当日领取")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    balance = _add_coins(user, record.coin)
    log_coin(db, user_id, CoinSource.WHEEL, record.coin,
             remark=f"抽中{record.prize_label}", balance_after=balance)
    record.status = "claimed"
    record.claimed_at = datetime.now()
    db.commit()

    row = (
        db.query(WheelChance)
        .filter(WheelChance.user_id == user_id, WheelChance.stat_date == date.today())
        .first()
    )
    return {
        "ok": True,
        "coin": record.coin,
        "label": record.prize_label,
        "coin_balance": balance,
        "chances_left": _chances_left(cfg, row),
        "ad_chance_left": _ad_chance_left(cfg, row),
        "message": f"{record.coin}金币已到账",
    }


@router.get("/api/wheel/records")
def wheel_records(
    page: int = 1,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """我的抽奖记录，每页20条"""
    user_id = _current_user_id(current_user)
    page = max(1, page)
    size = 20
    rows = (
        db.query(WheelDrawRecord)
        .filter(WheelDrawRecord.user_id == user_id)
        .order_by(WheelDrawRecord.id.desc())
        .offset((page - 1) * size)
        .limit(size + 1)
        .all()
    )
    has_more = len(rows) > size
    rows = rows[:size]

    status_text = {"pending": "待领取", "claimed": "已到账", "expired": "已过期"}
    return {
        "list": [
            {
                "id": r.id,
                "label": r.prize_label,
                "coin": r.coin,
                "status": r.status,
                "status_text": status_text.get(r.status, r.status),
                "time": r.created_at.strftime("%m-%d %H:%M") if r.created_at else "",
            }
            for r in rows
        ],
        "has_more": has_more,
    }
