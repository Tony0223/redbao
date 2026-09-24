"""
提现补贴业务。

活动状态：
- none   没开启 / 没设结束时间 / 没有启用的档位 → App 隐藏补贴模块
- active 进行中
- ended  已过结束时间 → App 显示"活动已结束"

补贴次数：按"该用户该档位没失败的申请"计，被驳回或打款失败的次数自动退回。

金币流水：这里是自己扣金币的（没走 crud.create_withdrawal_request），
所以扣币要在本文件里记一条 WITHDRAW 流水。
退币不用管，走的是 withdrawal_service._fail_and_refund()，那边已经记了。
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud, models
from app.coin_models import CoinSource, log_coin
from app.withdrawal_service import WithdrawalError, is_authorized

S = models.WithdrawalStatus


def get_status(db: Session, now: datetime | None = None):
    """返回 (status, end_at)。"""
    enabled = crud.get_setting(db, "subsidy_enabled", "false").strip().lower() == "true"
    end_raw = crud.get_setting(db, "subsidy_end_at", "").strip()
    if not enabled or not end_raw:
        return "none", None
    try:
        end_at = datetime.fromisoformat(end_raw)
    except ValueError:
        return "none", None

    has_tier = db.query(models.SubsidyTier.id).filter(models.SubsidyTier.enabled.is_(True)).first()
    if has_tier is None:
        return "none", end_at

    now = now or datetime.now()
    return ("active" if now < end_at else "ended"), end_at


def is_active(db: Session) -> bool:
    return get_status(db)[0] == "active"


def coins_per_yuan(db: Session) -> int:
    return int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000"))


def single_limit_fen(db: Session) -> int:
    try:
        return int(round(float(crud.get_setting(db, "wxpay_single_limit_yuan", "50")) * 100))
    except ValueError:
        return 5000


def calc_subsidy_fen(tier: models.SubsidyTier) -> int:
    return tier.withdraw_fen * tier.percent // 100


def calc_coin_amount(tier: models.SubsidyTier, rate: int) -> int:
    return tier.withdraw_fen * rate // 100


def _used_counts(db: Session, user_id: int) -> dict:
    rows = (
        db.query(models.WithdrawalRequest.tier_id, func.count(models.WithdrawalRequest.id))
        .filter(
            models.WithdrawalRequest.user_id == user_id,
            models.WithdrawalRequest.tier_id.isnot(None),
            models.WithdrawalRequest.status != S.FAILED,
        )
        .group_by(models.WithdrawalRequest.tier_id)
        .all()
    )
    return {tier_id: count for tier_id, count in rows}


def list_tiers_for_user(db: Session, user_id: int) -> list:
    rate = coins_per_yuan(db)
    used = _used_counts(db, user_id)
    tiers = (
        db.query(models.SubsidyTier)
        .filter(models.SubsidyTier.enabled.is_(True))
        .order_by(models.SubsidyTier.sort_order, models.SubsidyTier.id)
        .all()
    )
    result = []
    for t in tiers:
        subsidy = calc_subsidy_fen(t)
        result.append({
            "id": t.id,
            "withdraw_fen": t.withdraw_fen,
            "percent": t.percent,
            "subsidy_fen": subsidy,
            "arrive_fen": t.withdraw_fen + subsidy,
            "coin_amount": calc_coin_amount(t, rate),
            "limit": t.per_user_limit,
            "used": used.get(t.id, 0),
        })
    return result


def create_subsidy_withdrawal(db: Session, user: models.User, tier_id: int) -> models.WithdrawalRequest:
    status, _ = get_status(db)
    if status == "ended":
        raise WithdrawalError("活动已结束")
    if status != "active":
        raise WithdrawalError("补贴活动未开启")

    tier = (
        db.query(models.SubsidyTier)
        .filter(models.SubsidyTier.id == tier_id, models.SubsidyTier.enabled.is_(True))
        .first()
    )
    if tier is None:
        raise WithdrawalError("这个档位不存在或已下架")

    # 锁住用户这一行：防止连点提交导致超次数、超余额
    locked_user = (
        db.query(models.User)
        .filter(models.User.id == user.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not is_authorized(locked_user):
        raise WithdrawalError("请先绑定微信收款")

    if tier.per_user_limit > 0:
        used = _used_counts(db, locked_user.id).get(tier.id, 0)
        if used >= tier.per_user_limit:
            raise WithdrawalError("这一档的补贴次数已用完")

    subsidy = calc_subsidy_fen(tier)
    if tier.withdraw_fen + subsidy > single_limit_fen(db):
        raise WithdrawalError("该档位金额超出单笔转账上限，请联系客服")

    coin_amount = calc_coin_amount(tier, coins_per_yuan(db))
    if locked_user.coin_balance < coin_amount:
        raise WithdrawalError("金币余额不足")

    locked_user.coin_balance -= coin_amount
    db.add(locked_user)

    req = models.WithdrawalRequest(
        user_id=locked_user.id,
        coin_amount=coin_amount,
        yuan_amount=tier.withdraw_fen,
        tier_id=tier.id,
        subsidy_fen=subsidy,
        status=S.PENDING,
    )
    db.add(req)
    log_coin(
        db, locked_user.id, CoinSource.WITHDRAW, -coin_amount,
        remark=f"补贴档位提现{tier.withdraw_fen / 100:.2f}元(补贴{tier.percent}%)",
        balance_after=locked_user.coin_balance,
    )
    db.commit()
    db.refresh(req)
    return req
