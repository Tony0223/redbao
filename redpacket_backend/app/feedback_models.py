"""
用户意见反馈。

昵称存的是【快照】：提交那一刻把 users.nickname 抄一份进来，
而不是后台查的时候 join users。这样用户改了昵称、或者注销之后，
历史反馈里还是当时那个名字，回溯和对账都清楚。

手机号和邮箱二选一必填，校验在 routers/feedback.py 里做。
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class FeedbackStatus:
    PENDING = "pending"      # 待处理
    REPLIED = "replied"      # 已回复
    CLOSED = "closed"        # 已关闭（无需回复的那种）


STATUS_LABELS = {
    FeedbackStatus.PENDING: "待处理",
    FeedbackStatus.REPLIED: "已回复",
    FeedbackStatus.CLOSED: "已关闭",
}

STATUS_COLORS = {
    FeedbackStatus.PENDING: "#f59e0b",
    FeedbackStatus.REPLIED: "#16a34a",
    FeedbackStatus.CLOSED: "#6b7280",
}


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    user_id = Column(Integer, index=True, nullable=False, comment="提交人用户ID")
    nickname = Column(String(64), nullable=True, comment="提交时的微信昵称快照")
    content = Column(Text, nullable=False, comment="反馈内容")
    phone = Column(String(20), nullable=True, comment="手机号，和邮箱二选一")
    email = Column(String(120), nullable=True, comment="邮箱，和手机号二选一")
    status = Column(
        String(16), default=FeedbackStatus.PENDING, nullable=False, index=True,
        comment="pending待处理/replied已回复/closed已关闭",
    )
    reply = Column(Text, nullable=True, comment="后台回复内容，用户在App里能看到")
    created_at = Column(DateTime, default=datetime.now, index=True, comment="提交时间")
    replied_at = Column(DateTime, nullable=True, comment="处理时间")
