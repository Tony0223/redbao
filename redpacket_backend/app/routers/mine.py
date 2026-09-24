"""
"我的"页相关接口。

    GET  /api/user/me/profile     头部信息：昵称、用户ID、师傅ID、余额、今日已赚、红包领取次数
    GET  /api/user/coin_logs      收入明细（分页，默认只看入账）
    GET  /api/app/config          客服联系方式 + 版本信息 + 汇率门槛
    GET  /api/app/content/{key}   平台公告 / 隐私政策 / 用户协议，内容后台可配
    POST /api/user/deactivate     注销账号

注销做的是逻辑注销：把 openid 改成不可能再匹配的占位串、清空 token 和昵称、余额清零，
并记一条流水。这样同一个微信再登录会当成全新用户，老数据也不会被翻出来。
各大应用市场都强制要求有这个入口，没有过不了审。
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud, models
from app.auth import get_current_user
from app.coin_models import SOURCE_LABELS, CoinLog, CoinSource, log_coin
from app.database import get_db

router = APIRouter(tags=["mine"])

# 后台可配的图文页面：key -> (页面标题, 设置项key)
CONTENT_PAGES = {
    "notice": ("平台公告", "notice_content"),
    "privacy": ("隐私政策", "privacy_content"),
    "agreement": ("用户协议", "agreement_content"),
}


@router.get("/api/user/me/profile")
def my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """我的页头部。师傅ID就是邀请人的用户ID，没有师傅就返回0。"""
    coins_per_yuan = int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000") or 100000)

    today_earned = (
        db.query(func.coalesce(func.sum(CoinLog.coins), 0))
        .filter(
            CoinLog.user_id == current_user.id,
            CoinLog.coins > 0,
            func.date(CoinLog.created_at) == date.today(),
        )
        .scalar()
        or 0
    )

    return {
        "user_id": current_user.id,
        "nickname": current_user.nickname or ("用户" + str(current_user.id)),
        "avatar_url": current_user.avatar_url or "",
        "master_id": current_user.invited_by_user_id or 0,
        "invite_code": current_user.invite_code or "",
        "coin_balance": current_user.coin_balance,
        "coins_per_yuan": coins_per_yuan,
        "today_earned_coins": int(today_earned),
        "today_earned_yuan": round(int(today_earned) / coins_per_yuan, 2),
        "balance_yuan": round(current_user.coin_balance / coins_per_yuan, 2),
        "ad_watch_count": current_user.ad_watch_count or 0,
    }


@router.get("/api/user/coin_logs")
def my_coin_logs(
    page: int = Query(1, ge=1),
    only_income: bool = Query(True, description="只看入账，默认true"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """收入明细，每页20条。"""
    size = 20
    q = db.query(CoinLog).filter(CoinLog.user_id == current_user.id)
    if only_income:
        q = q.filter(CoinLog.coins > 0)

    rows = (
        q.order_by(CoinLog.id.desc())
        .offset((page - 1) * size)
        .limit(size + 1)
        .all()
    )
    has_more = len(rows) > size
    rows = rows[:size]

    total_income = (
        db.query(func.coalesce(func.sum(CoinLog.coins), 0))
        .filter(CoinLog.user_id == current_user.id, CoinLog.coins > 0)
        .scalar()
        or 0
    )

    return {
        "total_income_coins": int(total_income),
        "list": [
            {
                "id": r.id,
                "source": r.source,
                "source_text": SOURCE_LABELS.get(r.source, "其他"),
                "coins": r.coins,
                "remark": r.remark or "",
                "time": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in rows
        ],
        "has_more": has_more,
    }


@router.get("/api/app/config")
def app_config(db: Session = Depends(get_db)):
    """客服方式、版本信息、汇率门槛。不需要登录，启动时就能拉。"""
    return {
        "contact_qq": crud.get_setting(db, "contact_qq", ""),
        "contact_wechat": crud.get_setting(db, "contact_wechat", ""),
        "contact_phone": crud.get_setting(db, "contact_phone", ""),
        "latest_version_name": crud.get_setting(db, "latest_version_name", ""),
        "latest_version_code": int(crud.get_setting(db, "latest_version_code", "1") or 1),
        "update_notes": crud.get_setting(db, "update_notes", ""),
        "update_url": crud.get_setting(db, "update_url", ""),
        "force_update": crud.get_setting(db, "force_update", "false") == "true",
        "coins_per_yuan": int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000") or 100000),
        "min_withdraw_coins": int(crud.get_setting(db, "min_withdraw_coins", "500000") or 500000),
    }


@router.get("/api/app/content/{key}")
def app_content(key: str, db: Session = Depends(get_db)):
    """平台公告 / 隐私政策 / 用户协议，内容在后台 /admin/content 维护。"""
    if key not in CONTENT_PAGES:
        raise HTTPException(status_code=404, detail="页面不存在")
    title, setting_key = CONTENT_PAGES[key]
    return {
        "key": key,
        "title": title,
        "content": crud.get_setting(db, setting_key, ""),
    }


@router.post("/api/user/deactivate")
def deactivate_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """注销账号。不可恢复，客户端必须二次确认过再调。"""
    # 按 id 在当前 session 里重新查一次再改。
    # 依赖注入进来的 current_user 不一定挂在这个 session 上，直接改可能不落库。
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.openid and user.openid.startswith("deleted_"):
        raise HTTPException(status_code=400, detail="账号已注销")

    # 余额清零前先记一条流水，留个账
    if user.coin_balance:
        log_coin(
            db,
            user.id,
            CoinSource.ADMIN,
            -user.coin_balance,
            remark="账号注销，余额清零",
            balance_after=0,
        )

    # openid 换成占位串：保留唯一约束，同一个微信再登录会建全新用户，翻不出老数据
    user.openid = f"deleted_{user.id}_{int(datetime.now().timestamp())}"
    user.token = None
    user.nickname = "已注销用户"
    user.avatar_url = None
    user.coin_balance = 0
    user.wx_auth_no = None
    user.wx_auth_state = None
    user.wx_auth_id = None
    user.wx_auth_package = None
    db.commit()

    return {"success": True, "message": "账号已注销"}
