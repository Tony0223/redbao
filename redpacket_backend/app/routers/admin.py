"""
后台管理页面：
- /admin/reward-configs  查看/编辑看广告奖励规则（低区/高区）
- /admin/rebate-config   查看/编辑团长返利规则
- /admin/users           用户列表
- /admin/ad-logs         广告观看流水记录
- /admin/withdrawals     提现申请列表（当前需要手动标记处理状态，自动打款还没接）
- /admin/settings        App更新配置 + 客服联系方式 + 提现汇率/门槛

用HTTP Basic Auth做了个简单密码保护，账号密码从环境变量读，
不要把这个路径公开分享出去（够自己一个人用，不是严格意义上的多人权限后台）。
"""
import os
import secrets
import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud, models
import html
from urllib.parse import quote

from app import withdrawal_service
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

# 会话签名密钥：优先用独立env，否则退回admin密码派生，保证部署不配也能用
SESSION_SECRET = os.getenv("ADMIN_SESSION_SECRET", "") or (ADMIN_PASSWORD + "|redbao-admin")
COOKIE_NAME = "admin_session"
SESSION_MAX_AGE = 7 * 24 * 3600   # 登录保持7天

# 可分配给普通账号的菜单（key 与 /admin/<key> 路径一致）
MENU_ITEMS = [
    ("reward-configs", "看广告奖励"),
    ("rebate-config", "团长返利"),
    ("signin", "每日签到"),
    ("punch", "每日打卡"),
    ("bonus", "福利活动"),
    ("wheel", "幸运转盘"),
    ("users", "用户列表"),
    ("ad-logs", "广告流水"),
    ("withdrawals", "提现申请"),
    ("subsidy", "提现补贴"),
    ("content", "公告/协议"),
    ("feedback", "意见反馈"),
    ("settings", "App/客服设置"),
]
ALL_MENU_KEYS = [k for k, _ in MENU_ITEMS]
# 仅超管可见的“后台账号管理”菜单
SUPER_MENU_KEY = "admin-users"
SUPER_MENU_LABEL = "后台账号"

PAGE_SIZE = 50

AD_TYPE_LABELS = {
    models.AdType.REWARD_VIDEO: "激励视频",
    models.AdType.FEED: "信息流",
    models.AdType.INTERSTITIAL: "插屏",
    models.AdType.BANNER: "Banner",
}

WITHDRAWAL_STATUS_LABELS = {
    models.WithdrawalStatus.PENDING: ("待处理", "#f59e0b"),
    models.WithdrawalStatus.PROCESSING: ("打款中", "#2563eb"),
    models.WithdrawalStatus.SUCCESS: ("已成功", "#16a34a"),
    models.WithdrawalStatus.FAILED: ("失败", "#dc2626"),
}


# ==================== 会话(登录态) ====================

def _sign_session(username: str) -> str:
    raw = f"{username}|{int(time.time())}"
    b = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), b.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b}.{sig}"


def _read_session(token: str):
    """校验签名和有效期，返回用户名，非法返回 None。"""
    if not token or "." not in token:
        return None
    b, sig = token.rsplit(".", 1)
    expect = hmac.new(SESSION_SECRET.encode("utf-8"), b.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        raw = base64.urlsafe_b64decode(b.encode("ascii")).decode("utf-8")
        username, ts = raw.rsplit("|", 1)
    except Exception:
        return None
    if int(time.time()) - int(ts) > SESSION_MAX_AGE:
        return None
    return username


def _menu_key_for_path(path: str):
    """从请求路径取菜单key：/admin/<key>/... -> <key>；/admin 或 /admin/ -> None。"""
    p = path
    if p.startswith("/admin"):
        p = p[len("/admin"):]
    p = p.strip("/")
    if not p:
        return None
    return p.split("/")[0]


def verify_admin(request: Request, db: Session = Depends(get_db)):
    """登录态校验 + 菜单权限校验。未登录跳登录页，无权访问该菜单则403。"""
    username = _read_session(request.cookies.get(COOKIE_NAME))
    user = crud.get_admin_user(db, username) if username else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="未登录",
            headers={"Location": "/admin/login"},
        )
    key = _menu_key_for_path(request.url.path)
    if key == SUPER_MENU_KEY:
        if not user.is_super:
            raise HTTPException(status_code=403, detail="仅超级管理员可访问")
    elif key in ALL_MENU_KEYS and not user.is_super:
        allowed = [m for m in (user.allowed_menus or "").split(",") if m]
        if key not in allowed:
            raise HTTPException(status_code=403, detail="没有该菜单的访问权限")
    return user


def _visible_menus(user) -> list:
    """当前账号能看到的菜单列表 [(key,label,is_super_only)]。"""
    items = []
    for key, label in MENU_ITEMS:
        if user is None or user.is_super:
            items.append((key, label))
        else:
            allowed = [m for m in (user.allowed_menus or "").split(",") if m]
            if key in allowed:
                items.append((key, label))
    return items


def render_page(active: str, body: str, user=None) -> str:
    items = _visible_menus(user)
    nav_html = ""
    for key, label in items:
        selected = key == active
        nav_html += (
            f'<a href="/admin/{key}" style="display:block;padding:10px 16px;margin-bottom:2px;'
            f'text-decoration:none;font-size:14px;border-radius:8px;'
            f'{"background:#2563eb;color:#fff;font-weight:600;" if selected else "color:#374151;"}'
            f'">{label}</a>'
        )
    # 超管额外显示“后台账号”管理入口
    if user is not None and getattr(user, "is_super", False):
        selected = active == SUPER_MENU_KEY
        nav_html += (
            f'<a href="/admin/{SUPER_MENU_KEY}" style="display:block;padding:10px 16px;margin-bottom:2px;'
            f'text-decoration:none;font-size:14px;border-radius:8px;'
            f'{"background:#2563eb;color:#fff;font-weight:600;" if selected else "color:#374151;"}'
            f'">{SUPER_MENU_LABEL}</a>'
        )

    uname = html.escape(getattr(user, "username", "") or "")
    role = "超级管理员" if getattr(user, "is_super", False) else "管理员"
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>红包群后台</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f9fafb;margin:0;">
        <div style="display:flex;min-height:100vh;">
            <div style="width:200px;flex-shrink:0;background:#fff;border-right:1px solid #e5e7eb;
                padding:16px 10px;display:flex;flex-direction:column;">
                <div style="font-size:16px;font-weight:700;color:#111827;padding:8px 16px 16px;">红包群后台</div>
                <div style="flex:1;">{nav_html}</div>
                <div style="border-top:1px solid #f3f4f6;padding:12px 16px 4px;">
                    <div style="font-size:13px;color:#111827;">{uname}</div>
                    <div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">{role}</div>
                    <a href="/admin/logout" style="font-size:13px;color:#dc2626;text-decoration:none;">退出登录</a>
                </div>
            </div>
            <div style="flex:1;padding:32px;overflow-x:auto;">
                <div style="max-width:960px;">{body}</div>
            </div>
        </div>
    </body>
    </html>
    """


def render_table(headers: list, rows: list) -> str:
    head_html = "".join(
        f'<th style="text-align:left;padding:10px 12px;color:#6b7280;'
        f'font-size:13px;border-bottom:1px solid #e5e7eb;">{h}</th>'
        for h in headers
    )
    body_html = "".join(
        "<tr>" + "".join(
            f'<td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;'
            f'font-size:14px;color:#111827;">{cell}</td>'
            for cell in row
        ) + "</tr>"
        for row in rows
    )
    if not rows:
        body_html = (
            f'<tr><td colspan="{len(headers)}" style="padding:24px;text-align:center;'
            f'color:#9ca3af;">暂无数据</td></tr>'
        )
    return f"""
    <table style="width:100%;border-collapse:collapse;background:#fff;
        border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
        <thead><tr>{head_html}</tr></thead>
        <tbody>{body_html}</tbody>
    </table>
    """


def render_pagination(base_path: str, page: int, has_next: bool, extra_qs: str = "") -> str:
    prev_link = (
        f'<a href="{base_path}?page={page - 1}{extra_qs}" style="margin-right:16px;color:#2563eb;">← 上一页</a>'
        if page > 1 else '<span style="margin-right:16px;color:#d1d5db;">← 上一页</span>'
    )
    next_link = (
        f'<a href="{base_path}?page={page + 1}{extra_qs}" style="color:#2563eb;">下一页 →</a>'
        if has_next else '<span style="color:#d1d5db;">下一页 →</span>'
    )
    return f'<div style="margin-top:16px;">{prev_link}第{page}页{next_link}</div>'


def stat_card(label: str, value: str) -> str:
    return f"""
    <div style="flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;">
        <div style="color:#6b7280;font-size:13px;margin-bottom:6px;">{label}</div>
        <div style="color:#111827;font-size:24px;font-weight:700;">{value}</div>
    </div>
    """


def form_row(label: str, name: str, value, hint: str, input_type: str = "number") -> str:
    return f"""
    <div style="margin-bottom:16px;">
        <label style="display:block;font-weight:600;color:#374151;margin-bottom:4px;">{label}</label>
        <input type="{input_type}" name="{name}" value="{value}" required
            style="width:280px;padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;">
        <span style="color:#9ca3af;font-size:13px;margin-left:8px;">{hint}</span>
    </div>
    """


# ---------- 看广告奖励规则 ----------

def render_tier_form(config, saved: bool) -> str:
    tier_label = "低区" if config.tier == models.UserTier.LOW else "高区"
    saved_banner = (
        '<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
        'border-radius:8px;margin-bottom:16px;">✅ 已保存</div>'
        if saved else ""
    )
    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-bottom:24px;background:#fff;">
        <h2 style="margin-top:0;color:#111827;">{tier_label}收益配置</h2>
        {saved_banner}
        <form method="post" action="/admin/reward-configs/{config.tier.value}">
            {form_row("最小金币值", "min_coin", config.min_coin, "看一次广告能拿到的最小金币数")}
            {form_row("最大金币值(默认)", "max_coin_default", config.max_coin_default, "非游戏类广告的金币上限")}
            {form_row("最大金币值(游戏类广告)", "max_coin_game", config.max_coin_game, "游戏类广告单独的金币上限")}
            {form_row("插屏广告最大值", "interstitial_max_coin", config.interstitial_max_coin, "插屏广告单独设置的上限")}
            {form_row("看多少个广告赐福", "bonus_threshold_count", config.bonus_threshold_count, "每看满N个广告触发一次赐福，0表示不生效")}
            {form_row("赐福多少个", "bonus_amount", config.bonus_amount, "每次触发赐福额外发多少金币，0表示不生效")}
            <button type="submit" style="background:#2563eb;color:#fff;border:none;padding:10px 24px;
                border-radius:8px;font-size:14px;cursor:pointer;margin-top:8px;">保存{tier_label}配置</button>
        </form>
    </div>
    """


@router.get("/reward-configs", response_class=HTMLResponse)
def show_reward_configs(
    saved: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    low_config = crud.get_or_create_reward_config(db, models.UserTier.LOW)
    high_config = crud.get_or_create_reward_config(db, models.UserTier.HIGH)

    body = f"""
        <h1 style="color:#111827;">看广告奖励规则</h1>
        <p style="color:#6b7280;margin-bottom:24px;">改完点保存，App那边立刻按新数值生效，不用重新部署代码。</p>
        {render_tier_form(low_config, saved == "low")}
        {render_tier_form(high_config, saved == "high")}
    """
    return HTMLResponse(content=render_page("reward-configs", body, admin))


@router.post("/reward-configs/{tier}")
def update_reward_config(
    tier: str,
    min_coin: int = Form(...),
    max_coin_default: int = Form(...),
    max_coin_game: int = Form(...),
    interstitial_max_coin: int = Form(...),
    bonus_threshold_count: int = Form(...),
    bonus_amount: int = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    tier_enum = models.UserTier(tier)
    config = crud.get_or_create_reward_config(db, tier_enum)

    config.min_coin = min_coin
    config.max_coin_default = max_coin_default
    config.max_coin_game = max_coin_game
    config.interstitial_max_coin = interstitial_max_coin
    config.bonus_threshold_count = bonus_threshold_count
    config.bonus_amount = bonus_amount

    db.add(config)
    db.commit()

    return RedirectResponse(url=f"/admin/reward-configs?saved={tier}", status_code=303)


# ---------- 团长返利规则 ----------

@router.get("/rebate-config", response_class=HTMLResponse)
def show_rebate_config(
    saved: bool = False,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    config = crud.get_or_create_rebate_config(db)
    saved_banner = (
        '<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
        'border-radius:8px;margin-bottom:16px;">✅ 已保存</div>'
        if saved else ""
    )
    percentage_checked = "checked" if config.mode == models.RebateMode.PERCENTAGE else ""
    fixed_checked = "checked" if config.mode == models.RebateMode.FIXED else ""

    body = f"""
        <h1 style="color:#111827;">团长返利规则</h1>
        <p style="color:#6b7280;margin-bottom:24px;">
            团员（被邀请注册的用户）看广告拿到金币后，邀请他的团长按下面规则自动拿到抽成。
        </p>
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;background:#fff;">
            {saved_banner}
            <form method="post" action="/admin/rebate-config">
                <div style="margin-bottom:20px;">
                    <label style="display:block;font-weight:600;color:#374151;margin-bottom:8px;">抽成模式</label>
                    <label style="margin-right:24px;"><input type="radio" name="mode" value="percentage" {percentage_checked}> 比例抽成</label>
                    <label><input type="radio" name="mode" value="fixed" {fixed_checked}> 固定金额</label>
                </div>
                {form_row("比例抽成的百分比", "percentage_value", config.percentage_value, "团员本次拿到金币的百分之N归团长，比例模式下生效")}
                {form_row("固定抽成金额", "fixed_value", config.fixed_value, "团员每看一次广告，团长固定拿多少金币，固定模式下生效")}
                <button type="submit" style="background:#2563eb;color:#fff;border:none;padding:10px 24px;
                    border-radius:8px;font-size:14px;cursor:pointer;margin-top:8px;">保存配置</button>
            </form>
        </div>
    """
    return HTMLResponse(content=render_page("rebate-config", body, admin))


@router.post("/rebate-config")
def update_rebate_config(
    mode: str = Form(...),
    percentage_value: int = Form(...),
    fixed_value: int = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    config = crud.get_or_create_rebate_config(db)
    config.mode = models.RebateMode(mode)
    config.percentage_value = percentage_value
    config.fixed_value = fixed_value
    db.add(config)
    db.commit()
    return RedirectResponse(url="/admin/rebate-config?saved=true", status_code=303)


# ---------- 用户列表 ----------

@router.get("/users", response_class=HTMLResponse)
def show_users(
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_coins = db.query(func.sum(models.User.coin_balance)).scalar() or 0
    total_watches = db.query(func.sum(models.User.ad_watch_count)).scalar() or 0

    stats_html = f"""
    <div style="display:flex;gap:16px;margin-bottom:24px;">
        {stat_card("总用户数", str(total_users))}
        {stat_card("累计发放金币", f"{total_coins:,}")}
        {stat_card("累计看广告次数", f"{total_watches:,}")}
    </div>
    """

    users = (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
        .all()
    )
    has_next = len(users) > PAGE_SIZE
    users = users[:PAGE_SIZE]

    rows = [
        [
            str(u.id),
            u.nickname or "-",
            (u.openid[:16] + "...") if u.openid and len(u.openid) > 16 else (u.openid or "-"),
            f"{u.coin_balance:,}",
            "低区" if u.tier == models.UserTier.LOW else "高区",
            str(u.ad_watch_count),
            u.invite_code or "-",
            str(u.invited_by_user_id) if u.invited_by_user_id else "-",
            u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-",
        ]
        for u in users
    ]

    table_html = render_table(
        ["ID", "昵称", "openid", "金币余额", "档位", "看广告次数", "邀请码", "团长ID", "注册时间"], rows
    )
    pagination_html = render_pagination("/admin/users", page, has_next)

    body = f"""
        <h1 style="color:#111827;">用户列表</h1>
        {stats_html}
        {table_html}
        {pagination_html}
    """
    return HTMLResponse(content=render_page("users", body, admin))


# ---------- 广告流水 ----------

@router.get("/ad-logs", response_class=HTMLResponse)
def show_ad_logs(
    page: int = Query(1, ge=1),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    query = db.query(models.AdWatchLog)
    if user_id is not None:
        query = query.filter(models.AdWatchLog.user_id == user_id)

    logs = (
        query.order_by(models.AdWatchLog.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
        .all()
    )
    has_next = len(logs) > PAGE_SIZE
    logs = logs[:PAGE_SIZE]

    rows = [
        [
            str(log.id),
            str(log.user_id),
            AD_TYPE_LABELS.get(log.ad_type, log.ad_type.value),
            "是" if log.is_game_ad else "否",
            f"{log.reward_amount:,}",
            f"{log.bonus_amount:,}" if log.bonus_amount else "-",
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "-",
        ]
        for log in logs
    ]

    table_html = render_table(
        ["ID", "用户ID", "广告类型", "游戏类广告", "基础奖励", "赐福", "时间"], rows
    )
    extra_qs = f"&user_id={user_id}" if user_id is not None else ""
    pagination_html = render_pagination("/admin/ad-logs", page, has_next, extra_qs)

    filter_hint = (
        f'<p style="color:#6b7280;">当前只看用户ID {user_id} 的记录，'
        f'<a href="/admin/ad-logs" style="color:#2563eb;">清除筛选</a></p>'
        if user_id is not None else ""
    )

    body = f"""
        <h1 style="color:#111827;">广告观看流水</h1>
        {filter_hint}
        {table_html}
        {pagination_html}
    """
    return HTMLResponse(content=render_page("ad-logs", body, admin))


# ---------- 提现申请 ----------

def _action_button(url: str, label: str, color: str, confirm_text: str = "") -> str:
    onsubmit = f' onsubmit="return confirm(\'{confirm_text}\');"' if confirm_text else ""
    return f"""
    <form method="post" action="{url}" style="display:inline;margin-right:6px;"{onsubmit}>
        <button type="submit" style="background:{color};color:#fff;border:none;
            padding:4px 10px;border-radius:6px;font-size:12px;cursor:pointer;">{label}</button>
    </form>
    """


@router.get("/withdrawals", response_class=HTMLResponse)
def show_withdrawals(
    page: int = Query(1, ge=1),
    status_filter: str = Query(None, alias="status"),
    msg: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    query = db.query(models.WithdrawalRequest)
    if status_filter:
        query = query.filter(models.WithdrawalRequest.status == models.WithdrawalStatus(status_filter))

    requests = (
        query.order_by(models.WithdrawalRequest.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
        .all()
    )
    has_next = len(requests) > PAGE_SIZE
    requests = requests[:PAGE_SIZE]

    user_ids = {r.user_id for r in requests}
    users = (
        {u.id: u for u in db.query(models.User).filter(models.User.id.in_(user_ids)).all()}
        if user_ids else {}
    )

    rows = []
    for r in requests:
        label, color = WITHDRAWAL_STATUS_LABELS.get(r.status, (r.status.value, "#6b7280"))
        status_badge = f'<span style="color:{color};font-weight:600;">{label}</span>'

        user = users.get(r.user_id)
        bind_badge = (
            '<span style="color:#16a34a;">已绑定</span>'
            if user and withdrawal_service.is_authorized(user)
            else '<span style="color:#9ca3af;">未绑定</span>'
        )

        subsidy = r.subsidy_fen or 0
        yuan_text = f"{r.yuan_amount / 100:.2f}元" + (f" + 补贴{subsidy / 100:.2f}元" if subsidy else "")
        action_html = "-"
        if r.status == models.WithdrawalStatus.PENDING:
            action_html = (
                _action_button(f"/admin/withdrawals/{r.id}/approve", "审核通过并打款", "#16a34a",
                               f"确认向用户{r.user_id}打款{yuan_text}？")
                + _action_button(f"/admin/withdrawals/{r.id}/reject", "驳回", "#dc2626",
                                 f"确认驳回？金币会退回给用户{r.user_id}")
            )
        elif r.status == models.WithdrawalStatus.PROCESSING:
            action_html = _action_button(f"/admin/withdrawals/{r.id}/sync", "查单刷新", "#2563eb")

        rows.append([
            str(r.id),
            str(r.user_id),
            bind_badge,
            f"{r.coin_amount:,}",
            yuan_text,
            status_badge,
            html.escape(r.remark or "-"),
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-",
            action_html,
        ])

    table_html = render_table(
        ["ID", "用户ID", "微信收款", "提现金币", "折合金额", "状态", "备注", "申请时间", "操作"], rows
    )
    pagination_html = render_pagination("/admin/withdrawals", page, has_next)

    msg_banner = (
        f'<div style="background:#eff6ff;color:#1e40af;padding:10px 16px;'
        f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>'
        if msg else ""
    )

    body = f"""
        <h1 style="color:#111827;">提现申请</h1>
        <p style="color:#6b7280;margin-bottom:16px;">
            点"审核通过并打款"会立刻通过微信商家转账打到用户零钱（用户需已绑定微信收款）。
            显示"打款中"的单子，稍后点"查单刷新"获取微信最终结果。
        </p>
        {msg_banner}
        {table_html}
        {pagination_html}
    """
    return HTMLResponse(content=render_page("withdrawals", body, admin))


def _get_withdrawal(db: Session, request_id: int) -> models.WithdrawalRequest:
    req = db.query(models.WithdrawalRequest).filter(models.WithdrawalRequest.id == request_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return req


def _redirect_with_msg(request_id: int, msg: str) -> RedirectResponse:
    return RedirectResponse(
        url="/admin/withdrawals?msg=" + quote(f"#{request_id}：{msg}"), status_code=303
    )


@router.post("/withdrawals/{request_id}/approve")
def approve_withdrawal(
    request_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    req = _get_withdrawal(db, request_id)
    try:
        msg = withdrawal_service.approve(db, req)
    except withdrawal_service.WithdrawalError as e:
        msg = str(e)
    return _redirect_with_msg(request_id, msg)


@router.post("/withdrawals/{request_id}/reject")
def reject_withdrawal(
    request_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    req = _get_withdrawal(db, request_id)
    try:
        msg = withdrawal_service.reject(db, req)
    except withdrawal_service.WithdrawalError as e:
        msg = str(e)
    return _redirect_with_msg(request_id, msg)


@router.post("/withdrawals/{request_id}/sync")
def sync_withdrawal(
    request_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    req = _get_withdrawal(db, request_id)
    try:
        msg = withdrawal_service.sync(db, req)
    except withdrawal_service.WithdrawalError as e:
        msg = str(e)
    return _redirect_with_msg(request_id, msg)

SETTINGS_SECTIONS = [
    ("App更新配置", [
        ("latest_version_name", "最新版本号", "text"),
        ("latest_version_code", "最新版本号(内部数字)", "number"),
        ("update_notes", "更新说明", "text"),
        ("update_url", "下载链接", "text"),
        ("force_update", "是否强制更新(true/false)", "text"),
    ]),
    ("客服联系方式", [
        ("contact_wechat", "客服微信号", "text"),
        ("contact_qq", "客服QQ号", "text"),
        ("contact_phone", "客服电话", "text"),
    ]),
    ("提现设置", [
        ("exchange_rate_coins_per_yuan", "多少金币=1元", "number"),
        ("min_withdraw_coins", "最低提现金币数", "number"),
    ]),
    ("首页横幅", [
        ("home_banner_title", "横幅主标题", "text"),
        ("home_banner_subtitle", "横幅副标题", "text"),
    ]),
]


@router.get("/settings", response_class=HTMLResponse)
def show_settings(
    saved: bool = False,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    saved_banner = (
        '<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
        'border-radius:8px;margin-bottom:16px;">✅ 已保存</div>'
        if saved else ""
    )

    sections_html = ""
    for section_title, fields in SETTINGS_SECTIONS:
        rows_html = ""
        for key, label, input_type in fields:
            value = crud.get_setting(db, key, "")
            rows_html += form_row(label, key, value, "", input_type=input_type)
        sections_html += f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-bottom:24px;background:#fff;">
            <h2 style="margin-top:0;color:#111827;">{section_title}</h2>
            {rows_html}
        </div>
        """

    body = f"""
        <h1 style="color:#111827;">App更新 / 客服 / 提现设置</h1>
        {saved_banner}
        <form method="post" action="/admin/settings">
            {sections_html}
            <button type="submit" style="background:#2563eb;color:#fff;border:none;padding:10px 24px;
                border-radius:8px;font-size:14px;cursor:pointer;">保存全部设置</button>
        </form>
    """
    return HTMLResponse(content=render_page("settings", body, admin))


@router.post("/settings")
async def update_settings(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    form = await request.form()
    all_keys = [key for _, fields in SETTINGS_SECTIONS for key, _, _ in fields]
    for key in all_keys:
        if key in form:
            crud.set_setting(db, key, str(form[key]))
    return RedirectResponse(url="/admin/settings?saved=true", status_code=303)


# ==================== 登录 / 登出 / 首页跳转 ====================

def render_login(error: str = "") -> str:
    err_html = (
        f'<div style="color:#dc2626;font-size:13px;margin-bottom:12px;">{html.escape(error)}</div>'
        if error else ""
    )
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>后台登录</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#f3f4f6;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;">
        <form method="post" action="/admin/login"
            style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:32px;width:320px;">
            <div style="font-size:20px;font-weight:700;color:#111827;margin-bottom:20px;text-align:center;">红包群后台</div>
            {err_html}
            <label style="display:block;font-size:13px;color:#374151;margin-bottom:4px;">账号</label>
            <input name="username" required style="width:100%;box-sizing:border-box;padding:10px;
                border:1px solid #d1d5db;border-radius:8px;margin-bottom:14px;" />
            <label style="display:block;font-size:13px;color:#374151;margin-bottom:4px;">密码</label>
            <input name="password" type="password" required style="width:100%;box-sizing:border-box;padding:10px;
                border:1px solid #d1d5db;border-radius:8px;margin-bottom:20px;" />
            <button type="submit" style="width:100%;background:#2563eb;color:#fff;border:none;padding:11px;
                border-radius:8px;font-size:15px;cursor:pointer;">登录</button>
        </form>
    </body>
    </html>
    """


@router.get("/login", response_class=HTMLResponse)
def login_page(error: int = 0):
    return HTMLResponse(content=render_login("账号或密码不对" if error else ""))


@router.post("/login")
def login_submit(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = crud.get_admin_user(db, username.strip())
    if user is None or not crud.verify_password(password, user.password_hash):
        return RedirectResponse(url="/admin/login?error=1", status_code=303)
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        COOKIE_NAME, _sign_session(user.username),
        max_age=SESSION_MAX_AGE, httponly=True, samesite="lax", path="/admin",
    )
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/admin")
    return resp


@router.get("")
def admin_index(user=Depends(verify_admin)):
    menus = _visible_menus(user)
    if menus:
        target = menus[0][0]
    elif user.is_super:
        target = SUPER_MENU_KEY
    else:
        target = "login"
    return RedirectResponse(url=f"/admin/{target}", status_code=303)


# ==================== 后台账号管理（仅超管） ====================

def _menu_checkboxes(selected: set) -> str:
    boxes = ""
    for key, label in MENU_ITEMS:
        checked = "checked" if key in selected else ""
        boxes += (
            f'<label style="display:inline-block;width:150px;margin:4px 0;font-size:13px;color:#374151;">'
            f'<input type="checkbox" name="menus" value="{key}" {checked}/> {label}</label>'
        )
    return boxes


@router.get("/admin-users", response_class=HTMLResponse)
def admin_users_page(
    saved: int = 0,
    err: str = "",
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    menu_label = dict(MENU_ITEMS)
    rows = []
    for u in crud.list_admin_users(db):
        role = "超级管理员" if u.is_super else "管理员"
        if u.is_super:
            menus_txt = "全部"
            edit_html = "—"
        else:
            allowed = [m for m in (u.allowed_menus or "").split(",") if m]
            menus_txt = "、".join(menu_label.get(m, m) for m in allowed) or "—"
            edit_html = (
                f'<details><summary style="cursor:pointer;color:#2563eb;font-size:13px;">编辑</summary>'
                f'<form method="post" action="/admin/admin-users/{u.id}/update" style="margin-top:8px;">'
                f'<div style="margin-bottom:8px;">{_menu_checkboxes(set(allowed))}</div>'
                f'<input name="password" placeholder="重置密码(留空不改)" style="padding:6px;'
                f'border:1px solid #d1d5db;border-radius:6px;margin-right:8px;" />'
                f'<button type="submit" style="background:#2563eb;color:#fff;border:none;padding:6px 14px;'
                f'border-radius:6px;cursor:pointer;">保存</button></form>'
                f'<form method="post" action="/admin/admin-users/{u.id}/delete" style="margin-top:8px;" '
                f'onsubmit="return confirm(\'确定删除该账号？\')">'
                f'<button type="submit" style="background:#dc2626;color:#fff;border:none;padding:6px 14px;'
                f'border-radius:6px;cursor:pointer;">删除账号</button></form></details>'
            )
        rows.append([html.escape(u.username), role, menus_txt, edit_html])

    table = render_table(["账号", "角色", "可见菜单", "操作"], rows)

    tip = ""
    if saved:
        tip = ('<div style="background:#dcfce7;color:#166534;padding:10px 16px;border-radius:8px;'
               'margin-bottom:16px;">✅ 已保存</div>')
    elif err == "dup":
        tip = ('<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;border-radius:8px;'
               'margin-bottom:16px;">账号已存在</div>')
    elif err == "empty":
        tip = ('<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;border-radius:8px;'
               'margin-bottom:16px;">账号和密码不能为空</div>')

    create_form = f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-top:24px;background:#fff;">
        <h2 style="margin-top:0;color:#111827;font-size:16px;">新建后台账号</h2>
        <form method="post" action="/admin/admin-users/create">
            <div style="margin-bottom:12px;">
                <input name="username" placeholder="账号" required style="padding:8px;border:1px solid #d1d5db;
                    border-radius:6px;margin-right:8px;" />
                <input name="password" placeholder="密码" required style="padding:8px;border:1px solid #d1d5db;
                    border-radius:6px;" />
            </div>
            <div style="margin-bottom:8px;font-size:13px;color:#6b7280;">可见菜单：</div>
            <div style="margin-bottom:12px;">{_menu_checkboxes(set())}</div>
            <button type="submit" style="background:#16a34a;color:#fff;border:none;padding:9px 20px;
                border-radius:8px;font-size:14px;cursor:pointer;">创建账号</button>
        </form>
    </div>
    """
    body = f'<h1 style="color:#111827;">后台账号管理</h1>{tip}{table}{create_form}'
    return HTMLResponse(content=render_page(SUPER_MENU_KEY, body, admin))


@router.post("/admin-users/create")
async def admin_users_create(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = (form.get("password") or "").strip()
    if not username or not password:
        return RedirectResponse(url="/admin/admin-users?err=empty", status_code=303)
    if crud.get_admin_user(db, username):
        return RedirectResponse(url="/admin/admin-users?err=dup", status_code=303)
    menus = ",".join(m for m in form.getlist("menus") if m in ALL_MENU_KEYS)
    crud.create_admin_user(db, username, password, is_super=False, allowed_menus=menus)
    return RedirectResponse(url="/admin/admin-users?saved=1", status_code=303)


@router.post("/admin-users/{uid}/update")
async def admin_users_update(
    uid: int,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    target = crud.get_admin_user_by_id(db, uid)
    if target is not None and not target.is_super:
        form = await request.form()
        password = (form.get("password") or "").strip()
        menus = ",".join(m for m in form.getlist("menus") if m in ALL_MENU_KEYS)
        crud.update_admin_user(db, uid, allowed_menus=menus, password=(password or None))
    return RedirectResponse(url="/admin/admin-users?saved=1", status_code=303)


@router.post("/admin-users/{uid}/delete")
def admin_users_delete(
    uid: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    crud.delete_admin_user(db, uid)
    return RedirectResponse(url="/admin/admin-users?saved=1", status_code=303)
