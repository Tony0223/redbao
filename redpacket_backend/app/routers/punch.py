"""
每日打卡接口：
- GET  /api/punch/info   打卡状态、时间段、奖金池、我的名次、规则文案
- POST /api/punch        打卡（App看完激励视频后调）
- GET  /api/punch/rank   今日打卡排行榜
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, punch_service
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/punch", tags=["punch"])


@router.get("/info")
def punch_info(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return punch_service.get_info(db, current_user)


@router.post("")
def do_punch(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return punch_service.punch(db, current_user)
    except punch_service.PunchError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rank")
def punch_rank(
    day: str = Query(None, description="日期 YYYY-MM-DD，不传就是今天"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    target = date.today()
    if day:
        try:
            target = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式不对")
    return punch_service.get_rank(db, current_user, target)