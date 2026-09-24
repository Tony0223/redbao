"""
意见反馈接口。

    POST /api/feedback        提交反馈
    GET  /api/feedback/my     我的反馈记录（含后台回复）

校验规则：
- 内容 5~500 字
- 手机号和邮箱【至少填一个】，填了的那个要格式对
- 同一用户 60 秒内只能提交一次，当天最多 5 条，防刷
"""
import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.feedback_models import STATUS_LABELS, Feedback, FeedbackStatus

router = APIRouter(tags=["feedback"])

CONTENT_MIN = 5
CONTENT_MAX = 500
SUBMIT_INTERVAL_SECONDS = 60
DAILY_LIMIT = 5

# 国内手机号：1开头，第二位3-9，共11位
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


class FeedbackRequest(BaseModel):
    content: str
    phone: str = ""
    email: str = ""


@router.post("/api/feedback")
def submit_feedback(
    req: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    content = (req.content or "").strip()
    phone = (req.phone or "").strip()
    email = (req.email or "").strip()

    if len(content) < CONTENT_MIN:
        raise HTTPException(status_code=400, detail=f"反馈内容至少{CONTENT_MIN}个字")
    if len(content) > CONTENT_MAX:
        raise HTTPException(status_code=400, detail=f"反馈内容最多{CONTENT_MAX}个字")

    # 二选一必填
    if not phone and not email:
        raise HTTPException(status_code=400, detail="手机号和邮箱请至少填写一个，方便我们回复你")
    if phone and not PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="手机号格式不对，请填11位手机号")
    if email and not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不对")

    # 防刷：间隔 + 每日上限
    last = (
        db.query(Feedback)
        .filter(Feedback.user_id == current_user.id)
        .order_by(Feedback.id.desc())
        .first()
    )
    now = datetime.now()
    if last and last.created_at and (now - last.created_at).total_seconds() < SUBMIT_INTERVAL_SECONDS:
        raise HTTPException(status_code=400, detail="提交太频繁了，请稍后再试")

    today_count = (
        db.query(func.count(Feedback.id))
        .filter(
            Feedback.user_id == current_user.id,
            func.date(Feedback.created_at) == date.today(),
        )
        .scalar()
        or 0
    )
    if today_count >= DAILY_LIMIT:
        raise HTTPException(status_code=400, detail=f"今天最多提交{DAILY_LIMIT}条反馈，明天再来")

    fb = Feedback(
        user_id=current_user.id,
        nickname=current_user.nickname,   # 快照，之后改昵称不影响这条记录
        content=content,
        phone=phone or None,
        email=email or None,
        status=FeedbackStatus.PENDING,
        created_at=now,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    return {
        "success": True,
        "id": fb.id,
        "message": "反馈已提交，我们会尽快处理",
    }


@router.get("/api/feedback/my")
def my_feedback(
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """我的反馈记录，能看到后台回没回。每页20条。"""
    size = 20
    rows = (
        db.query(Feedback)
        .filter(Feedback.user_id == current_user.id)
        .order_by(Feedback.id.desc())
        .offset((page - 1) * size)
        .limit(size + 1)
        .all()
    )
    has_more = len(rows) > size
    rows = rows[:size]

    return {
        "list": [
            {
                "id": r.id,
                "content": r.content,
                "status": r.status,
                "status_text": STATUS_LABELS.get(r.status, r.status),
                "reply": r.reply or "",
                "time": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "replied_time": r.replied_at.strftime("%Y-%m-%d %H:%M") if r.replied_at else "",
            }
            for r in rows
        ],
        "has_more": has_more,
    }
