from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app import withdrawal_service as svc
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/withdrawal", tags=["withdrawal"])


def _status_text(r: models.WithdrawalRequest) -> str:
    value = r.status.value
    remark = r.remark or ""
    if value == "failed":
        if remark.startswith(svc.REJECT_REMARK):
            return "已驳回（金币已退回）"
        return "打款失败（金币已退回）"
    if value == "success" and svc.SUBSIDY_EXPIRED_REMARK in remark:
        return "已到账（活动已结束，未含补贴）"
    return {
        "pending": "审核中",
        "processing": "打款中",
        "success": "已到账",
    }.get(value, value)


@router.get("/info")
def withdrawal_info(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """提现页信息：是否已绑定微信收款、最低提现金币、汇率。"""
    auth_state = svc.refresh_auth_state(db, current_user)
    normal_min = int(crud.get_setting(db, "min_withdraw_coins", "500000"))
    newbie = crud.is_newbie_withdraw_eligible(db, current_user)
    newbie_coins = int(crud.get_setting(db, "newbie_withdraw_coins", "30000"))
    # 新人首提时，最低门槛就是首提固定金额，App 沿用 min_withdraw_coins 逻辑即可
    effective_min = newbie_coins if newbie else normal_min
    return {
        "authorized": auth_state == svc.AUTH_EFFECTIVE,
        "auth_state": auth_state,
        "min_withdraw_coins": effective_min,
        "normal_min_withdraw_coins": normal_min,
        "coins_per_yuan": int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000")),
        "is_newbie_withdraw": newbie,
        "newbie_withdraw_coins": newbie_coins,
        "newbie_ad_count": int(crud.get_setting(db, "newbie_withdraw_ad_count", "5")),
    }


@router.post("/auth/apply")
def apply_auth(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """发起微信免确认收款授权，返回 App 拉起授权页需要的参数。"""
    try:
        return svc.apply_authorization(db, current_user)
    except svc.WithdrawalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/request", response_model=schemas.WithdrawalRequestResponse)
def request_withdrawal(
    payload: schemas.WithdrawalRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """普通提现（自由填金额，无补贴）。"""
    if not svc.is_authorized(current_user):
        raise HTTPException(status_code=400, detail="请先绑定微信收款")

    if crud.is_newbie_withdraw_eligible(db, current_user):
        # 新人首提：固定为首提金额，忽略前端传的数额，防止改包提更多
        coin_amount = int(crud.get_setting(db, "newbie_withdraw_coins", "30000"))
        if current_user.coin_balance < coin_amount:
            raise HTTPException(status_code=400, detail="金币还不够首提门槛，再看几次广告就能提啦")
    else:
        coin_amount = payload.coin_amount
        min_withdraw = int(crud.get_setting(db, "min_withdraw_coins", "500000"))
        if coin_amount < min_withdraw:
            raise HTTPException(status_code=400, detail=f"最低需要{min_withdraw}金币才能申请提现")
        if coin_amount > current_user.coin_balance:
            raise HTTPException(status_code=400, detail="金币余额不足")

    request = crud.create_withdrawal_request(db, current_user, coin_amount)
    return schemas.WithdrawalRequestResponse(
        id=request.id,
        coin_amount=request.coin_amount,
        yuan_amount=request.yuan_amount,
        status=request.status.value,
        created_at=request.created_at,
    )


@router.get("/list")
def list_withdrawals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """查自己的提现申请记录，最新在前。App端解析 data['list']。"""
    records = crud.list_withdrawals_by_user(db, current_user.id)
    items = []
    for r in records:
        items.append({
            "id": r.id,
            "coin_amount": r.coin_amount,
            "yuan_amount": r.yuan_amount,          # 提现金额，单位分
            "subsidy_fen": r.subsidy_fen or 0,     # 补贴，单位分（活动结束后审核的为0）
            "status": r.status.value,
            "status_text": _status_text(r),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        })
    return {"list": items}


@router.post("/notify/authorization")
async def authorization_notify(request: Request, db: Session = Depends(get_db)):
    """微信免确认收款授权结果回调（不需要登录，靠微信签名校验身份）。"""
    body = (await request.body()).decode("utf-8")
    if not svc.handle_auth_notify(db, request.headers, body):
        return JSONResponse(status_code=400, content={"code": "FAIL", "message": "验签失败"})
    return Response(status_code=204)