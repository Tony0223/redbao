"""
代理商分成的业务逻辑：邀请码、用户归属、eCPM 收益入库、统计、结算单。
金额单位都是“分”(Decimal)，展示时用 fen_to_yuan 换成元。
"""
import random
import string
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud, models
from app.agent_models import (
    AdRevenueLog, Agent, AgentSettlement, AgentUser, SettlementStatus,
)

# App 上报的广告类型白名单
AD_TYPES = {"reward_video", "fullscreen", "feed", "banner", "splash"}
AD_TYPE_LABELS = {
    "reward_video": "激励视频",
    "fullscreen": "插全屏",
    "feed": "信息流",
    "banner": "Banner",
    "splash": "开屏",
}


class AgentError(Exception):
    pass


def fen_to_yuan(fen) -> str:
    return f"{(Decimal(fen or 0) / 100):.2f}"


def day_range(d: date):
    start = datetime(d.year, d.month, d.day)
    return start, start + timedelta(days=1)


def month_range(d: date):
    start = datetime(d.year, d.month, 1)
    nxt = datetime(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return start, nxt


# ==================== 代理 ====================

def generate_agent_code(db: Session) -> str:
    """6位邀请码，和用户邀请码、其他代理码都不能撞。"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=6))
        if crud.get_user_by_invite_code(db, code) is None and get_agent_by_code(db, code) is None:
            return code


def get_agent(db: Session, agent_id: int):
    return db.query(Agent).filter(Agent.id == agent_id).first()


def get_agent_by_code(db: Session, code: str):
    return db.query(Agent).filter(Agent.invite_code == code).first()


def get_agent_by_admin_user(db: Session, admin_user_id: int):
    return db.query(Agent).filter(Agent.admin_user_id == admin_user_id).first()


def list_agents(db: Session):
    return db.query(Agent).order_by(Agent.id.asc()).all()


def parse_ratio(raw) -> Decimal:
    try:
        ratio = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise AgentError("分成比例格式不对")
    if ratio < 0 or ratio > 100:
        raise AgentError("分成比例要在 0~100 之间")
    return ratio.quantize(Decimal("0.01"))


def create_agent(db: Session, name: str, ratio, contact: str, remark: str,
                 username: str, password: str) -> Agent:
    if not name:
        raise AgentError("代理名称不能为空")
    if not username or not password:
        raise AgentError("登录账号和密码不能为空")
    if crud.get_admin_user(db, username):
        raise AgentError("登录账号已存在")
    share_ratio = parse_ratio(ratio)
    admin_user = crud.create_admin_user(db, username, password, is_super=False, allowed_menus="")
    agent = Agent(
        name=name,
        invite_code=generate_agent_code(db),
        share_ratio=share_ratio,
        admin_user_id=admin_user.id,
        contact=contact or None,
        remark=remark or None,
        enabled=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent(db: Session, agent: Agent, name: str, ratio, contact: str, remark: str,
                 enabled: bool, password: str = None) -> Agent:
    if not name:
        raise AgentError("代理名称不能为空")
    agent.name = name
    agent.share_ratio = parse_ratio(ratio)
    agent.contact = contact or None
    agent.remark = remark or None
    agent.enabled = enabled
    db.commit()
    if password and agent.admin_user_id:
        crud.update_admin_user(db, agent.admin_user_id, password=password)
    return agent


# ==================== 用户归属 ====================

def bind_user_by_code(db: Session, user: models.User, code: str) -> bool:
    """新用户注册时用代理码进来的，归属到该代理。已归属的不改。"""
    if not code:
        return False
    agent = get_agent_by_code(db, code)
    if agent is None or not agent.enabled:
        return False
    if db.query(AgentUser).filter(AgentUser.user_id == user.id).first():
        return False
    db.add(AgentUser(user_id=user.id, agent_id=agent.id))
    db.commit()
    return True


def agent_id_of_user(db: Session, user_id: int):
    row = db.query(AgentUser.agent_id).filter(AgentUser.user_id == user_id).first()
    return row[0] if row else None


def count_agent_users(db: Session, agent_id: int, start=None, end=None) -> int:
    q = db.query(func.count(AgentUser.id)).filter(AgentUser.agent_id == agent_id)
    if start is not None:
        q = q.filter(AgentUser.created_at >= start, AgentUser.created_at < end)
    return int(q.scalar() or 0)


def list_agent_users(db: Session, agent_id: int, page: int, page_size: int):
    """代理名下用户，带每人累计贡献的广告收益(分)。返回 (rows, has_next)。"""
    revenue_sub = (
        db.query(
            AdRevenueLog.user_id.label("uid"),
            (func.sum(AdRevenueLog.ecpm_fen) / 1000).label("rev"),
            func.count(AdRevenueLog.id).label("shows"),
        )
        .filter(AdRevenueLog.agent_id == agent_id)
        .group_by(AdRevenueLog.user_id)
        .subquery()
    )
    rows = (
        db.query(models.User, AgentUser.created_at, revenue_sub.c.rev, revenue_sub.c.shows)
        .join(AgentUser, AgentUser.user_id == models.User.id)
        .outerjoin(revenue_sub, revenue_sub.c.uid == models.User.id)
        .filter(AgentUser.agent_id == agent_id)
        .order_by(AgentUser.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
        .all()
    )
    return rows[:page_size], len(rows) > page_size


# ==================== 收益 ====================

def record_revenue(db: Session, user: models.User, ad_type: str, ecpm_raw, sdk_name: str = None) -> bool:
    """记录一次广告展示的真实 eCPM。返回是否入库。"""
    if ad_type not in AD_TYPES:
        return False
    try:
        ecpm = Decimal(str(ecpm_raw).strip())
    except (InvalidOperation, ValueError):
        return False
    if not ecpm.is_finite() or ecpm <= 0:
        return False

    # 防刷：eCPM 封顶(客户端上报的值可被伪造)，单用户每天上报条数封顶
    cap = Decimal(crud.get_setting(db, "agent_ecpm_cap_fen", "50000") or "50000")
    if ecpm > cap:
        ecpm = cap
    daily_limit = int(crud.get_setting(db, "ad_revenue_daily_limit", "500") or 500)
    start, end = day_range(date.today())
    today_count = (
        db.query(func.count(AdRevenueLog.id))
        .filter(AdRevenueLog.user_id == user.id,
                AdRevenueLog.created_at >= start, AdRevenueLog.created_at < end)
        .scalar() or 0
    )
    if today_count >= daily_limit:
        return False

    db.add(AdRevenueLog(
        user_id=user.id,
        agent_id=agent_id_of_user(db, user.id),
        ad_type=ad_type,
        ecpm_fen=ecpm.quantize(Decimal("0.01")),
        sdk_name=(sdk_name or "")[:64] or None,
    ))
    db.commit()
    return True


def revenue_fen(db: Session, agent_id: int, start: datetime, end: datetime) -> Decimal:
    """某代理名下用户在 [start, end) 产生的广告收益(分)。"""
    total = (
        db.query(func.sum(AdRevenueLog.ecpm_fen))
        .filter(AdRevenueLog.agent_id == agent_id,
                AdRevenueLog.created_at >= start, AdRevenueLog.created_at < end)
        .scalar()
    )
    return Decimal(total or 0) / 1000


def daily_revenue(db: Session, agent_id: int, days: int = 30):
    """最近 N 天每日 (日期, 展示次数, 收益分)，最新在前。"""
    since = datetime.combine(date.today() - timedelta(days=days - 1), datetime.min.time())
    day_col = func.date(AdRevenueLog.created_at)
    rows = (
        db.query(day_col, func.count(AdRevenueLog.id), func.sum(AdRevenueLog.ecpm_fen))
        .filter(AdRevenueLog.agent_id == agent_id, AdRevenueLog.created_at >= since)
        .group_by(day_col)
        .order_by(day_col.desc())
        .all()
    )
    return [(d, int(c), Decimal(s or 0) / 1000) for d, c, s in rows]


def share_of(agent: Agent, fen: Decimal) -> Decimal:
    return fen * Decimal(agent.share_ratio or 0) / 100


# ==================== 结算单 ====================

def list_settlements(db: Session, agent_id: int = None):
    q = db.query(AgentSettlement)
    if agent_id:
        q = q.filter(AgentSettlement.agent_id == agent_id)
    return q.order_by(AgentSettlement.period_start.desc(), AgentSettlement.id.desc()).all()


def pending_share_fen(db: Session, agent_id: int) -> Decimal:
    total = (
        db.query(func.sum(AgentSettlement.share_fen))
        .filter(AgentSettlement.agent_id == agent_id,
                AgentSettlement.status == SettlementStatus.PENDING)
        .scalar()
    )
    return Decimal(total or 0)


def create_settlement(db: Session, agent: Agent, start: date, end: date, remark: str = "") -> AgentSettlement:
    if end < start:
        raise AgentError("结束日期不能早于开始日期")
    if end >= date.today():
        raise AgentError("只能结算到昨天(当天收益还在变化)")
    overlap = (
        db.query(AgentSettlement)
        .filter(AgentSettlement.agent_id == agent.id,
                AgentSettlement.period_start <= end,
                AgentSettlement.period_end >= start)
        .first()
    )
    if overlap:
        raise AgentError(
            f"和已有结算单时间重叠({overlap.period_start} ~ {overlap.period_end})，不能重复结算"
        )
    rev = revenue_fen(db, agent.id, day_range(start)[0], day_range(end)[1])
    settlement = AgentSettlement(
        agent_id=agent.id,
        period_start=start,
        period_end=end,
        revenue_fen=rev.quantize(Decimal("0.0001")),
        share_ratio=agent.share_ratio,
        share_fen=share_of(agent, rev).quantize(Decimal("0.0001")),
        status=SettlementStatus.PENDING,
        remark=remark or None,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


def mark_settled(db: Session, settlement_id: int) -> None:
    s = db.query(AgentSettlement).filter(AgentSettlement.id == settlement_id).first()
    if s is None:
        raise AgentError("结算单不存在")
    if s.status == SettlementStatus.SETTLED:
        return
    s.status = SettlementStatus.SETTLED
    s.settled_at = datetime.now()
    db.commit()
