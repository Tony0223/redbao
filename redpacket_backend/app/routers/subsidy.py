"""
平台补贴接口：
- GET  /api/subsidy/info       活动状态、结束时间、档位（含每人限次和已用次数）
- POST /api/subsidy/withdraw   按档位申请提现
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, subsidy_service
from app.auth import get_current_user
from app.database import get_db
from app.withdrawal_service import WithdrawalError

router = APIRouter(prefix="/api/subsidy", tags=["subsidy"])


class SubsidyWithdrawRequest(BaseModel):
    tier_id: int


def _ms(dt: datetime | None) -> int:
    return int(dt.timestamp() * 1000) if dt else 0


@router.get("/info")
def subsidy_info(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    now = datetime.now()
    status, end_at = subsidy_service.get_status(db, now)
    data = {
        "status": status,
        "end_at_ms": _ms(end_at),
        "server_now_ms": _ms(now),
        "tiers": [],
    }
    if status == "active":
        data["tiers"] = subsidy_service.list_tiers_for_user(db, current_user.id)
    return data


@router.post("/withdraw")
def subsidy_withdraw(
    payload: SubsidyWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        req = subsidy_service.create_subsidy_withdrawal(db, current_user, payload.tier_id)
    except WithdrawalError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": req.id,
        "coin_amount": req.coin_amount,
        "yuan_amount": req.yuan_amount,
        "subsidy_fen": req.subsidy_fen,
        "status": req.status.value,
    }