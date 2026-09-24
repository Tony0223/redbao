"""幸运转盘相关数据表。

只依赖 app.database.Base，不改动已有的 models.py。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class WheelConfig(Base):
    """转盘全局配置（单例表，id 固定为 1）"""

    __tablename__ = "wheel_configs"

    id = Column(Integer, primary_key=True, index=True, comment="主键，固定为1")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否开启转盘")
    daily_free_chances = Column(
        Integer, default=1, nullable=False, comment="每人每天免费抽奖次数"
    )
    ad_chance_enabled = Column(
        Boolean, default=True, nullable=False, comment="是否允许看激励视频换抽奖次数"
    )
    ad_chance_max = Column(
        Integer, default=9, nullable=False, comment="每天最多通过看广告换几次机会"
    )
    min_interval_seconds = Column(
        Integer, default=3, nullable=False, comment="两次抽奖之间最短间隔秒数，防刷"
    )
    rules_text = Column(Text, comment="抽奖规则文案")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="最后修改时间"
    )


class WheelPrize(Base):
    """转盘格子。启用的格子按 sort_order 排序，就是转盘上从0开始的格子序号。"""

    __tablename__ = "wheel_prizes"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    label = Column(String(32), nullable=False, comment="格子上显示的文案，如 66666 或 9999-18888")
    min_coin = Column(Integer, default=0, nullable=False, comment="奖励金币下限")
    max_coin = Column(Integer, default=0, nullable=False, comment="奖励金币上限，与下限相同就是固定值")
    weight = Column(
        Integer, default=10, nullable=False, comment="中奖权重，越大越容易中；按总权重归一，不用凑100"
    )
    daily_limit = Column(
        Integer, default=0, nullable=False, comment="每日全局限量，0表示不限量"
    )
    user_daily_limit = Column(
        Integer, default=0, nullable=False, comment="每人每日最多中几次，0表示不限"
    )
    sort_order = Column(Integer, default=0, nullable=False, comment="转盘上的位置，从小到大")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否启用这个格子")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class WheelChance(Base):
    """每人每天的抽奖次数账本，按日期天然重置"""

    __tablename__ = "wheel_chances"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    stat_date = Column(Date, index=True, nullable=False, comment="统计日期（自然日）")
    used_chances = Column(Integer, default=0, nullable=False, comment="今天已用掉的抽奖次数")
    ad_chances_got = Column(
        Integer, default=0, nullable=False, comment="今天通过看广告换到的额外次数"
    )
    last_draw_at = Column(DateTime, nullable=True, comment="最近一次抽奖时间，用于防刷")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (UniqueConstraint("user_id", "stat_date", name="uq_wheel_user_date"),)


class WheelDrawRecord(Base):
    """抽奖记录。draw 时写入 pending（不发币），看完广告 claim 后变 claimed 才到账。"""

    __tablename__ = "wheel_draw_records"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    user_id = Column(Integer, index=True, nullable=False, comment="用户ID")
    stat_date = Column(Date, index=True, nullable=False, comment="抽奖日期")
    prize_id = Column(Integer, index=True, nullable=False, comment="中的奖品ID")
    prize_label = Column(String(32), comment="中奖时的文案快照，奖品改名了也不影响历史记录")
    coin = Column(Integer, default=0, nullable=False, comment="本次实际中的金币（区间内随机）")
    status = Column(
        String(16), default="pending", nullable=False, index=True,
        comment="pending 待看广告领取 / claimed 已到账 / expired 过期未领"
    )
    created_at = Column(DateTime, default=datetime.now, index=True, comment="抽奖时间")
    claimed_at = Column(DateTime, nullable=True, comment="到账时间")
