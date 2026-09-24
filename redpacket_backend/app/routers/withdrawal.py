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
    return {
        "authorized": auth_state == svc.AUTH_EFFECTIVE,
        "auth_state": auth_state,
        "min_withdraw_coins": int(crud.get_setting(db, "min_withdraw_coins", "500000")),
        "coins_per_yuan": int(crud.get_setting(db, "exchange_rate_coins_per_yuan", "100000")),
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

    min_withdraw = int(crud.get_setting(db, "min_withdraw_coins", "500000"))
    if payload.coin_amount < min_withdraw:
        raise HTTPException(status_code=400, detail=f"最低需要{min_withdraw}金币才能申请提现")

    if payload.coin_amount > current_user.coin_balance:
        raise HTTPException(status_code=400, detail="金币余额不足")

    request = crud.create_withdrawal_request(db, current_user, payload.coin_amount)
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