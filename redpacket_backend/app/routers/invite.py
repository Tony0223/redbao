"""
邀请页接口：
- GET /api/invite/summary   推广统计（总人数、今日/昨日新增、今日/昨日活跃、今日/昨日收益）
- GET /api/invite/members   我邀请的人（分页，含每人贡献的返利）
- GET /api/invite/income    我的返利流水（分页）

"活跃"定义：当天至少看过一次广告。日期按服务器本地时间切分。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app import crud, models
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/invite", tags=["invite"])


def _day_range(days_ago: int):
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return start, start + timedelta(days=1)


def _display_name(user: models.User) -> str:
    return user.nickname or f"用户{user.id}"


def _fmt_time(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _count_new(db: Session, leader_id: int, start, end) -> int:
    return db.query(func.count(models.User.id)).filter(
        models.User.invited_by_user_id == leader_id,
        models.User.created_at >= start,
        models.User.created_at < end,
    ).scalar() or 0


def _count_active(db: Session, leader_id: int, start, end) -> int:
    return (
        db.query(func.count(distinct(models.AdWatchLog.user_id)))
        .join(models.User, models.User.id == models.AdWatchLog.user_id)
        .filter(
            models.User.invited_by_user_id == leader_id,
            models.AdWatchLog.created_at >= start,
            models.AdWatchLog.created_at < end,
        )
        .scalar() or 0
    )


def _sum_income(db: Session, leader_id: int, start, end) -> int:
    value = db.query(func.coalesce(func.sum(models.RebateLog.coin_amount), 0)).filter(
        models.RebateLog.leader_user_id == leader_id,
        models.RebateLog.created_at >= start,
        models.RebateLog.created_at < end,
    ).scalar()
    return int(value or 0)


@router.get("/summary")
def invite_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    today = _day_range(0)
    yesterday = _day_range(1)
    me = current_user.id

    total_count = db.query(func.count(models.User.id)).filter(
        models.User.invited_by_user_id == me
    ).scalar() or 0

    return {
        "user_id": me,
        "nickname": _display_name(current_user),
        "invite_code": current_user.invite_code or "",
        "total_count": total_count,
        "today_new": _count_new(db, me, *today),
        "yesterday_new": _count_new(db, me, *yesterday),
        "today_active": _count_active(db, me, *today),
        "yesterday_active": _count_active(db, me, *yesterday),
        "today_income_coins": _sum_income(db, me, *today),
        "yesterday_income_coins": _sum_income(db, me, *yesterday),
        "total_income_coins": current_user.total_rebate_coins or 0,
        "coins_per_yuan": int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000")),
    }


@router.get("/members")
def invite_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    contributed = (
        db.query(
            models.RebateLog.invitee_user_id.label("invitee_id"),
            func.sum(models.RebateLog.coin_amount).label("coins"),
        )
        .filter(models.RebateLog.leader_user_id == current_user.id)
        .group_by(models.RebateLog.invitee_user_id)
        .subquery()
    )
    rows = (
        db.query(models.User, func.coalesce(contributed.c.coins, 0))
        .outerjoin(contributed, contributed.c.invitee_id == models.User.id)
        .filter(models.User.invited_by_user_id == current_user.id)
        .order_by(models.User.created_at.desc(), models.User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
        .all()
    )
    has_more = len(rows) > page_size
    items = [
        {
            "user_id": u.id,
            "nickname": _display_name(u),
            "joined_at": _fmt_time(u.created_at),
            "contributed_coins": int(coins or 0),
        }
        for u, coins in rows[:page_size]
    ]
    return {"list": items, "has_more": has_more}


@router.get("/income")
def invite_income(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.RebateLog, models.User)
        .outerjoin(models.User, models.User.id == models.RebateLog.invitee_user_id)
        .filter(models.RebateLog.leader_user_id == current_user.id)
        .order_by(models.RebateLog.created_at.desc(), models.RebateLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
        .all()
    )
    has_more = len(rows) > page_size
    items = [
        {
            "coin_amount": log.coin_amount,
            "from_nickname": _display_name(u) if u else "已注销用户",
            "created_at": _fmt_time(log.created_at),
        }
        for log, u in rows[:page_size]
    ]
    return {"list": items, "has_more": has_more}