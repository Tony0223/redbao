"""福利活动（看满N次广告领M金币）相关数据表。

只依赖 app.database.Base，不改动已有的 models.py，避免影响现有表。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
)

from app.database import Base


class BonusActivityConfig(Base):
    """福利活动配置（单例表，只有一行，id 固定为 1）"""

    __tablename__ = "bonus_activity_configs"

    id = Column(Integer, primary_key=True, index=True, comment="主键，固定为1")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否开启福利活动")
    target_count = Column(Integer, default=20, nullable=False, comment="每日需看满的广告次数N")
    reward_coin = Column(Integer, default=20000, nullable=False, comment="看满后发放的金币数M")
    min_interval_seconds = Column(
        Integer, default=10, nullable=False, comment="两次计数之间的最短间隔秒数，防刷"
    )
    tips_text = Column(Text, comment="页面底部温馨提示文案，支持换行")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="最后修改时间"
    )


class BonusActivityProgress(Base):
    """用户每日进度，每人每天一行，按日期天然重置"""

    __tablename__ = "bonus_activity_progress"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    stat_date = Column(Date, index=True, nullable=False, comment="统计日期（自然日）")
    watch_count = Column(Integer, default=0, nullable=False, comment="当日已计数的观看次数")
    is_claimed = Column(Boolean, default=False, nullable=False, comment="当日奖励是否已发放")
    reward_coin = Column(Integer, default=0, nullable=False, comment="实际发放的金币数")
    claimed_at = Column(DateTime, nullable=True, comment="发放时间")
    last_watch_at = Column(DateTime, nullable=True, comment="最近一次计数时间，用于防刷间隔判断")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "stat_date", name="uq_bonus_user_date"),
    )
