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
    AdRevenueLog, Agent, AgentSettlement, AgentUser, RealRevenueDaily, SettlementStatus,
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


def prev_month_range(d: date):
    """上个月 [1号00:00, 本月1号00:00)"""
    this_start = datetime(d.year, d.month, 1)
    last_day = this_start - timedelta(days=1)
    return datetime(last_day.year, last_day.month, 1), this_start


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


def total_revenue_fen(db: Session, agent_id: int) -> Decimal:
    """某代理名下用户累计产生的广告收益(分)。"""
    total = (
        db.query(func.sum(AdRevenueLog.ecpm_fen))
        .filter(AdRevenueLog.agent_id == agent_id)
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


# ==================== 按穿山甲真实收益校正 ====================
# 当天系数 = min(1, 穿山甲收益API / 全体用户当天上报收益)；代理当天收益 = 上报收益 × 系数。
# 系数最大为 1：上报偏高时按比例压下来，偏低时不放大，保证分给代理的钱不超过穿山甲实际给的钱。
# 还没拉到真实收益的日期(比如今天)用上报值，界面上标“预估”。

def _as_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _daily_reported(db: Session, start_d: date, end_d: date, agent_id: int = None) -> dict:
    """[start_d, end_d] 每天的上报收益(分)。agent_id 为空表示全体用户(含非代理用户)。"""
    day_col = func.date(AdRevenueLog.created_at)
    q = (db.query(day_col, func.sum(AdRevenueLog.ecpm_fen))
         .filter(AdRevenueLog.created_at >= day_range(start_d)[0],
                 AdRevenueLog.created_at < day_range(end_d)[1]))
    if agent_id is not None:
        q = q.filter(AdRevenueLog.agent_id == agent_id)
    return {_as_date(d): Decimal(s or 0) / 1000 for d, s in q.group_by(day_col).all()}


def day_factors(db: Session, start_d: date, end_d: date) -> dict:
    """有真实收益数据的日期 → 校正系数。"""
    real = (db.query(RealRevenueDaily)
            .filter(RealRevenueDaily.report_date >= start_d, RealRevenueDaily.report_date <= end_d)
            .all())
    if not real:
        return {}
    reported = _daily_reported(db, start_d, end_d)
    factors = {}
    for r in real:
        rep = reported.get(_as_date(r.report_date), Decimal(0))
        real_fen = Decimal(r.revenue_fen or 0)
        factors[_as_date(r.report_date)] = Decimal(1) if rep <= 0 else min(Decimal(1), real_fen / rep)
    return factors


def first_revenue_date(db: Session, agent_id: int = None):
    q = db.query(func.min(AdRevenueLog.created_at))
    if agent_id is not None:
        q = q.filter(AdRevenueLog.agent_id == agent_id)
    v = q.scalar()
    return _as_date(v) if v else None


def calibrated_revenue(db: Session, agent_id: int, start_d: date, end_d: date):
    """
    代理在 [start_d, end_d](含首尾)的收益(分)。
    返回 (收益, 其中预估部分, 缺真实数据的日期列表)。只有代理当天有上报收益的日期才算“缺”。
    """
    if end_d < start_d:
        return Decimal(0), Decimal(0), []
    reported = _daily_reported(db, start_d, end_d, agent_id)
    if not reported:
        return Decimal(0), Decimal(0), []
    factors = day_factors(db, start_d, end_d)
    total = est = Decimal(0)
    missing = []
    for d, v in reported.items():
        if v <= 0:
            continue
        if d in factors:
            total += v * factors[d]
        else:
            total += v
            est += v
            missing.append(d)
    return total, est, sorted(missing)


def calibrated_total(db: Session, agent_id: int):
    first = first_revenue_date(db, agent_id)
    if first is None:
        return Decimal(0), Decimal(0), []
    return calibrated_revenue(db, agent_id, first, date.today())


def calibrated_daily(db: Session, agent_id: int, days: int = 30):
    """最近 N 天每日 (日期, 展示次数, 上报收益分, 校正后收益分, 系数或None)，最新在前。系数为 None = 还没校正(预估)。"""
    rows = daily_revenue(db, agent_id, days)
    if not rows:
        return []
    start_d = min(_as_date(d) for d, _, _ in rows)
    factors = day_factors(db, start_d, date.today())
    out = []
    for d, cnt, rev in rows:
        dd = _as_date(d)
        f = factors.get(dd)
        out.append((dd, cnt, rev, rev * f if f is not None else rev, f))
    return out


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
    # 按穿山甲真实收益校正后的金额结算；期间有任何一天还没拉到真实收益就不让生成
    rev, _est, missing = calibrated_revenue(db, agent.id, start, end)
    if missing:
        shown = "、".join(str(d) for d in missing[:10]) + (" 等" if len(missing) > 10 else "")
        raise AgentError(
            f"以下日期还没有穿山甲真实收益数据，不能生成结算单：{shown}。"
            f"请到“穿山甲真实收益”页面拉取后再结算"
        )
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


def delete_settlement(db: Session, settlement_id: int) -> None:
    """删除结算单：只允许删“待结算”的(生成错了可以重来)，已结算的不能删。"""
    s = db.query(AgentSettlement).filter(AgentSettlement.id == settlement_id).first()
    if s is None:
        raise AgentError("结算单不存在")
    if s.status == SettlementStatus.SETTLED:
        raise AgentError("已结算的结算单不能删除")
    db.delete(s)
    db.commit()
