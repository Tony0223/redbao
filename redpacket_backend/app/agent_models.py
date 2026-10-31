"""
代理商分成。

- Agent：代理商。有自己的专属邀请码，用户通过它注册就归属这个代理；
  share_ratio 是分成比例(百分比)，每个代理单独设；admin_user_id 是代理登录后台用的账号。
- AgentUser：用户归属代理的映射(单独一张表，不改 users 表结构，create_all 直接建)。
- AdRevenueLog：App 每次广告展示上报的真实 eCPM 流水。所有用户都记，
  agent_id 是上报那一刻的归属快照(非代理用户为空)。单次收益(分) = ecpm_fen / 1000。
- AgentSettlement：结算单。后台按代理+时间段生成，冻结当时的收益和比例，
  线下打款后手动标记已结算。

金额统一存“分”，Numeric 保留小数，避免浮点误差；展示时再换算成元。
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, func,
)

from app.database import Base


class SettlementStatus:
    PENDING = "pending"   # 待结算
    SETTLED = "settled"   # 已结算(已线下打款)


SETTLEMENT_STATUS_LABELS = {
    SettlementStatus.PENDING: ("待结算", "#f59e0b"),
    SettlementStatus.SETTLED: ("已结算", "#16a34a"),
}


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, comment="代理名称")
    invite_code = Column(String(16), unique=True, index=True, nullable=False, comment="代理专属邀请码")
    share_ratio = Column(Numeric(5, 2), nullable=False, default=0, comment="分成比例，百分比，如30.00")
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), unique=True, nullable=True,
                           comment="代理登录后台的账号")
    contact = Column(String(128), nullable=True, comment="联系方式")
    remark = Column(String(255), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())


class AgentUser(Base):
    __tablename__ = "agent_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class AdRevenueLog(Base):
    __tablename__ = "ad_revenue_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(Integer, nullable=True, index=True, comment="上报时归属的代理快照")
    ad_type = Column(String(32), nullable=False)
    ecpm_fen = Column(Numeric(12, 2), nullable=False, comment="真实eCPM，单位分/千次展示")
    sdk_name = Column(String(64), nullable=True, comment="实际出广告的ADN")
    created_at = Column(DateTime, server_default=func.now(), index=True)


class AgentSettlement(Base):
    __tablename__ = "agent_settlements"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False, comment="含当天")
    revenue_fen = Column(Numeric(14, 4), nullable=False, default=0, comment="期间名下用户产生的广告收益")
    share_ratio = Column(Numeric(5, 2), nullable=False, comment="生成时的分成比例快照")
    share_fen = Column(Numeric(14, 4), nullable=False, default=0, comment="应付代理金额")
    status = Column(String(16), nullable=False, default=SettlementStatus.PENDING)
    remark = Column(String(255), nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
