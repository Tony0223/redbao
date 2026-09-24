"""
福利页接口：
- GET  /api/welfare/signin/info   签到信息（今日已赚、周期、每天奖励、已签几天）
- POST /api/welfare/signin        签到领金币（App看完激励视频后调）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, signin_service
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/welfare", tags=["welfare"])


@router.get("/signin/info")
def signin_info(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return signin_service.get_info(db, current_user)


@router.post("/signin")
def sign_in(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return signin_service.sign_in(db, current_user)
    except signin_service.SignInError as e:
        raise HTTPException(status_code=400, detail=str(e))