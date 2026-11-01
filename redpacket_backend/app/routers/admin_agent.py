"""
代理商后台页面。

管理端(超管，或被分配了“代理商管理”菜单的管理员)：
- /admin/agents                    代理列表 + 新建代理(同时创建代理登录账号)
- /admin/agents/{id}/update        修改名称/比例/联系方式/启停/重置密码
- /admin/agents/settlements        结算单：按代理+时间段生成，线下打款后标记已结算

代理商账号(只看自己的)：
- /admin/agent-users               我的用户 + 收益概览
- /admin/agent-bills               我的账单：每日收益明细 + 结算单

收益口径：App 每次广告展示上报的真实 eCPM，单次收益 = eCPM / 1000 (分)。
"""
import html
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app import agent_service as svc
from app.agent_models import SETTLEMENT_STATUS_LABELS, SettlementStatus
from app.database import get_db
from app.routers.admin import (
    render_page, render_pagination, render_table, stat_card, verify_admin,
)

router = APIRouter(prefix="/admin", tags=["admin-agent"])

PAGE_SIZE = 50

INPUT_STYLE = "padding:8px;border:1px solid #d1d5db;border-radius:6px;"
BTN_STYLE = ("border:none;padding:8px 18px;border-radius:6px;font-size:14px;"
             "cursor:pointer;color:#fff;")


def _tip(msg: str, ok: bool = True) -> str:
    if not msg:
        return ""
    bg, fg = ("#dcfce7", "#166534") if ok else ("#fee2e2", "#991b1b")
    return (f'<div style="background:{bg};color:{fg};padding:10px 16px;border-radius:8px;'
            f'margin-bottom:16px;">{html.escape(msg)}</div>')


def _invite_link(request: Request, code: str) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return f"https://{host}/i/{code}"


def _qrcode_response(text: str, filename: str, download: bool) -> Response:
    """把邀请链接生成二维码 PNG。segno 是纯 Python 零依赖库，服务器端生成，不依赖外部 CDN。"""
    try:
        import segno  # 局部导入：服务器没装时只影响二维码，不影响后台其他功能
    except ImportError:
        return Response("服务器未安装 segno，请在后端目录执行 pip install -r requirements.txt",
                        status_code=500, media_type="text/plain; charset=utf-8")
    import io
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="png", scale=12, border=3)
    disposition = "attachment" if download else "inline"
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


def _status_badge(status: str) -> str:
    label, color = SETTLEMENT_STATUS_LABELS.get(status, (status, "#6b7280"))
    return f'<span style="color:{color};font-weight:600;">{label}</span>'


def _redirect(path: str, msg: str = "", ok: bool = True) -> RedirectResponse:
    qs = f"?msg={quote(msg)}&ok={1 if ok else 0}" if msg else ""
    return RedirectResponse(url=path + qs, status_code=303)


# ==================== 管理端：代理列表 ====================

@router.get("/agents", response_class=HTMLResponse)
def agents_page(
    request: Request,
    msg: str = "",
    ok: int = 1,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    month_start, month_end = svc.month_range(date.today())
    rows = []
    for a in svc.list_agents(db):
        login = "—"
        if a.admin_user_id:
            from app import crud
            au = crud.get_admin_user_by_id(db, a.admin_user_id)
            login = html.escape(au.username) if au else "—"
        month_rev = svc.revenue_fen(db, a.id, month_start, month_end)
        link = _invite_link(request, a.invite_code)
        status = ('<span style="color:#16a34a;">启用</span>' if a.enabled
                  else '<span style="color:#dc2626;">停用</span>')
        edit_html = f"""
        <details><summary style="cursor:pointer;color:#2563eb;font-size:13px;">编辑</summary>
          <form method="post" action="/admin/agents/{a.id}/update" style="margin-top:8px;line-height:2.4;">
            名称 <input name="name" value="{html.escape(a.name)}" required style="{INPUT_STYLE}width:120px;" /><br>
            分成比例 <input name="share_ratio" value="{a.share_ratio}" required style="{INPUT_STYLE}width:70px;" /> %<br>
            联系方式 <input name="contact" value="{html.escape(a.contact or '')}" style="{INPUT_STYLE}width:140px;" /><br>
            备注 <input name="remark" value="{html.escape(a.remark or '')}" style="{INPUT_STYLE}width:160px;" /><br>
            <label><input type="checkbox" name="enabled" {"checked" if a.enabled else ""}/> 启用</label><br>
            重置密码 <input name="password" placeholder="留空不改" style="{INPUT_STYLE}width:120px;" /><br>
            <button type="submit" style="{BTN_STYLE}background:#2563eb;">保存</button>
          </form>
        </details>"""
        rows.append([
            a.id,
            html.escape(a.name),
            f'<b>{a.invite_code}</b><br><span style="font-size:12px;color:#6b7280;">{html.escape(link)}</span>'
            f'<br><a href="/admin/agents/{a.id}/qrcode.png?download=1" style="font-size:12px;color:#2563eb;">下载推广二维码</a>',
            f"{a.share_ratio}%",
            svc.count_agent_users(db, a.id),
            f"¥{svc.fen_to_yuan(month_rev)}",
            f"¥{svc.fen_to_yuan(svc.share_of(a, month_rev))}",
            f"¥{svc.fen_to_yuan(svc.pending_share_fen(db, a.id))}",
            login,
            status,
            edit_html,
        ])
    table = render_table(
        ["ID", "名称", "专属邀请码/链接", "比例", "名下用户", "本月收益", "本月应分", "待结算",
         "登录账号", "状态", "操作"],
        rows,
    )
    create_form = f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-top:24px;background:#fff;">
      <h2 style="margin-top:0;color:#111827;font-size:16px;">新建代理商</h2>
      <form method="post" action="/admin/agents/create" style="line-height:2.6;">
        <input name="name" placeholder="代理名称" required style="{INPUT_STYLE}" />
        <input name="share_ratio" placeholder="分成比例%，如30" required style="{INPUT_STYLE}width:150px;" />
        <input name="contact" placeholder="联系方式(选填)" style="{INPUT_STYLE}" /><br>
        <input name="username" placeholder="代理登录账号" required style="{INPUT_STYLE}" />
        <input name="password" placeholder="登录密码" required style="{INPUT_STYLE}" />
        <input name="remark" placeholder="备注(选填)" style="{INPUT_STYLE}" /><br>
        <button type="submit" style="{BTN_STYLE}background:#16a34a;">创建代理</button>
        <span style="font-size:12px;color:#6b7280;margin-left:8px;">
          创建后自动生成专属邀请码；用户通过该邀请链接注册即归属此代理。</span>
      </form>
    </div>
    """
    nav = ('<div style="margin-bottom:16px;"><a href="/admin/agents/settlements" '
           'style="color:#2563eb;">→ 代理结算单</a></div>')
    body = (f'<h1 style="color:#111827;">代理商管理</h1>{_tip(msg, bool(ok))}{nav}'
            f'<div style="font-size:13px;color:#6b7280;margin-bottom:12px;">'
            f'收益=名下用户广告展示的真实eCPM累计；应分=收益×比例。</div>{table}{create_form}')
    return HTMLResponse(content=render_page("agents", body, admin))


@router.get("/agents/{agent_id}/qrcode.png")
def agent_qrcode_admin(
    agent_id: int,
    request: Request,
    download: int = 0,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        return Response("代理不存在", status_code=404, media_type="text/plain; charset=utf-8")
    return _qrcode_response(_invite_link(request, agent.invite_code),
                            f"agent_{agent.invite_code}.png", bool(download))


@router.post("/agents/create")
async def agents_create(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    form = await request.form()
    try:
        agent = svc.create_agent(
            db,
            name=(form.get("name") or "").strip(),
            ratio=form.get("share_ratio") or "",
            contact=(form.get("contact") or "").strip(),
            remark=(form.get("remark") or "").strip(),
            username=(form.get("username") or "").strip(),
            password=(form.get("password") or "").strip(),
        )
    except svc.AgentError as e:
        return _redirect("/admin/agents", str(e), ok=False)
    return _redirect("/admin/agents", f"已创建代理「{agent.name}」，邀请码 {agent.invite_code}")


@router.post("/agents/{agent_id}/update")
async def agents_update(
    agent_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        return _redirect("/admin/agents", "代理不存在", ok=False)
    form = await request.form()
    try:
        svc.update_agent(
            db, agent,
            name=(form.get("name") or "").strip(),
            ratio=form.get("share_ratio") or "",
            contact=(form.get("contact") or "").strip(),
            remark=(form.get("remark") or "").strip(),
            enabled=form.get("enabled") == "on",
            password=(form.get("password") or "").strip() or None,
        )
    except svc.AgentError as e:
        return _redirect("/admin/agents", str(e), ok=False)
    return _redirect("/admin/agents", "已保存")


# ==================== 管理端：结算单 ====================

@router.get("/agents/settlements", response_class=HTMLResponse)
def settlements_page(
    agent_id: int = 0,
    msg: str = "",
    ok: int = 1,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agents = svc.list_agents(db)
    agent_names = {a.id: a.name for a in agents}
    rows = []
    for s in svc.list_settlements(db, agent_id or None):
        if s.status == SettlementStatus.PENDING:
            action = (f'<form method="post" action="/admin/agents/settlements/{s.id}/settle" '
                      f'onsubmit="return confirm(\'确认已线下打款给代理？\')" style="margin:0;">'
                      f'<button type="submit" style="{BTN_STYLE}background:#16a34a;padding:5px 12px;">'
                      f'标记已结算</button></form>')
        else:
            action = s.settled_at.strftime("%Y-%m-%d %H:%M") if s.settled_at else "—"
        rows.append([
            s.id,
            html.escape(agent_names.get(s.agent_id, str(s.agent_id))),
            f"{s.period_start} ~ {s.period_end}",
            f"¥{svc.fen_to_yuan(s.revenue_fen)}",
            f"{s.share_ratio}%",
            f"<b>¥{svc.fen_to_yuan(s.share_fen)}</b>",
            _status_badge(s.status),
            html.escape(s.remark or ""),
            action,
        ])
    table = render_table(
        ["ID", "代理", "结算周期", "期间收益", "比例", "应付代理", "状态", "备注", "操作/结算时间"],
        rows,
    )
    options = "".join(
        f'<option value="{a.id}" {"selected" if a.id == agent_id else ""}>{html.escape(a.name)}</option>'
        for a in agents
    )
    filter_form = f"""
    <form method="get" action="/admin/agents/settlements" style="margin-bottom:16px;">
      筛选代理 <select name="agent_id" style="{INPUT_STYLE}"><option value="0">全部</option>{options}</select>
      <button type="submit" style="{BTN_STYLE}background:#6b7280;">筛选</button>
    </form>"""
    gen_options = "".join(f'<option value="{a.id}">{html.escape(a.name)}</option>' for a in agents)
    create_form = f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-top:24px;background:#fff;">
      <h2 style="margin-top:0;color:#111827;font-size:16px;">生成结算单</h2>
      <form method="post" action="/admin/agents/settlements/create" style="line-height:2.6;">
        代理 <select name="agent_id" required style="{INPUT_STYLE}">{gen_options}</select>
        开始 <input type="date" name="start" required style="{INPUT_STYLE}" />
        结束 <input type="date" name="end" required style="{INPUT_STYLE}" />
        <input name="remark" placeholder="备注(选填)" style="{INPUT_STYLE}" />
        <button type="submit" style="{BTN_STYLE}background:#2563eb;">生成</button>
        <div style="font-size:12px;color:#6b7280;">
          按所选时间段(含首尾两天)统计该代理名下用户的广告收益，按代理当前比例计算应付金额并冻结；
          只能结算到昨天，同一代理时间段不能重叠。</div>
      </form>
    </div>"""
    body = (f'<h1 style="color:#111827;">代理结算单</h1>{_tip(msg, bool(ok))}'
            f'<div style="margin-bottom:16px;"><a href="/admin/agents" style="color:#2563eb;">← 返回代理商管理</a></div>'
            f'{filter_form}{table}{create_form}')
    return HTMLResponse(content=render_page("agents", body, admin))


@router.post("/agents/settlements/create")
async def settlements_create(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    form = await request.form()
    agent = svc.get_agent(db, int(form.get("agent_id") or 0))
    if agent is None:
        return _redirect("/admin/agents/settlements", "请选择代理", ok=False)
    try:
        start = date.fromisoformat(form.get("start") or "")
        end = date.fromisoformat(form.get("end") or "")
    except ValueError:
        return _redirect("/admin/agents/settlements", "日期格式不对", ok=False)
    try:
        s = svc.create_settlement(db, agent, start, end, (form.get("remark") or "").strip())
    except svc.AgentError as e:
        return _redirect("/admin/agents/settlements", str(e), ok=False)
    return _redirect("/admin/agents/settlements",
                     f"已生成：{agent.name} {s.period_start}~{s.period_end} 应付 ¥{svc.fen_to_yuan(s.share_fen)}")


@router.post("/agents/settlements/{settlement_id}/settle")
def settlements_settle(
    settlement_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    try:
        svc.mark_settled(db, settlement_id)
    except svc.AgentError as e:
        return _redirect("/admin/agents/settlements", str(e), ok=False)
    return _redirect("/admin/agents/settlements", "已标记为已结算")


# ==================== 代理端：我的用户 ====================

def _agent_overview(db: Session, agent) -> str:
    today = date.today()
    d_start, d_end = svc.day_range(today)
    m_start, m_end = svc.month_range(today)
    today_rev = svc.revenue_fen(db, agent.id, d_start, d_end)
    month_rev = svc.revenue_fen(db, agent.id, m_start, m_end)
    cards = "".join([
        stat_card("名下用户", str(svc.count_agent_users(db, agent.id))),
        stat_card("今日新增", str(svc.count_agent_users(db, agent.id, d_start, d_end))),
        stat_card("今日收益 / 预计分成",
                  f"¥{svc.fen_to_yuan(today_rev)} / ¥{svc.fen_to_yuan(svc.share_of(agent, today_rev))}"),
        stat_card("本月收益 / 预计分成",
                  f"¥{svc.fen_to_yuan(month_rev)} / ¥{svc.fen_to_yuan(svc.share_of(agent, month_rev))}"),
        stat_card("待结算", f"¥{svc.fen_to_yuan(svc.pending_share_fen(db, agent.id))}"),
    ])
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;">{cards}</div>'


@router.get("/agent-users", response_class=HTMLResponse)
def agent_users_page(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agent = admin.agent
    rows_data, has_next = svc.list_agent_users(db, agent.id, page, PAGE_SIZE)
    rows = []
    for user, joined_at, rev, shows in rows_data:
        rows.append([
            user.id,
            html.escape(user.nickname or "—"),
            joined_at.strftime("%Y-%m-%d %H:%M") if joined_at else "—",
            user.ad_watch_count or 0,
            int(shows or 0),
            f"¥{svc.fen_to_yuan(rev or 0)}",
        ])
    table = render_table(["用户ID", "昵称", "注册时间", "累计看广告", "广告展示", "累计贡献收益"], rows)
    link = _invite_link(request, agent.invite_code)
    info = (f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;'
            f'margin-bottom:20px;font-size:14px;color:#374151;line-height:1.9;display:flex;gap:24px;'
            f'flex-wrap:wrap;align-items:center;">'
            f'<div style="flex:1;min-width:260px;">'
            f'代理：<b>{html.escape(agent.name)}</b>　分成比例：<b>{agent.share_ratio}%</b><br>'
            f'专属邀请码：<b>{agent.invite_code}</b><br>邀请链接：<b>{html.escape(link)}</b><br>'
            f'<span style="color:#6b7280;font-size:12px;">拉人方式：①把邀请链接发到微信群/朋友圈；'
            f'②保存右侧二维码做海报，扫码即可下载；③直接把邀请码告诉用户，'
            f'让他在 App 登录页的“邀请码”里填写。用户微信登录注册后即归属到你名下。</span>'
            f'</div>'
            f'<div style="text-align:center;">'
            f'<img src="/admin/agent-users/qrcode.png" alt="推广二维码" '
            f'style="width:150px;height:150px;border:1px solid #e5e7eb;border-radius:8px;"><br>'
            f'<a href="/admin/agent-users/qrcode.png?download=1" style="font-size:13px;color:#2563eb;">'
            f'下载推广二维码</a></div>'
            f'</div>')
    body = (f'<h1 style="color:#111827;">我的用户</h1>{info}{_agent_overview(db, agent)}{table}'
            f'{render_pagination("/admin/agent-users", page, has_next)}')
    return HTMLResponse(content=render_page("agent-users", body, admin))


@router.get("/agent-users/qrcode.png")
def agent_qrcode_self(
    request: Request,
    download: int = 0,
    admin=Depends(verify_admin),
):
    agent = admin.agent
    return _qrcode_response(_invite_link(request, agent.invite_code),
                            f"invite_{agent.invite_code}.png", bool(download))


# ==================== 代理端：我的账单 ====================

@router.get("/agent-bills", response_class=HTMLResponse)
def agent_bills_page(
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agent = admin.agent
    daily_rows = [
        [str(d), shows, f"¥{svc.fen_to_yuan(rev)}", f"¥{svc.fen_to_yuan(svc.share_of(agent, rev))}"]
        for d, shows, rev in svc.daily_revenue(db, agent.id, 30)
    ]
    daily_table = render_table(["日期", "广告展示次数", "收益", "预计分成"], daily_rows)

    settle_rows = [
        [
            f"{s.period_start} ~ {s.period_end}",
            f"¥{svc.fen_to_yuan(s.revenue_fen)}",
            f"{s.share_ratio}%",
            f"<b>¥{svc.fen_to_yuan(s.share_fen)}</b>",
            _status_badge(s.status),
            s.settled_at.strftime("%Y-%m-%d %H:%M") if s.settled_at else "—",
            html.escape(s.remark or ""),
        ]
        for s in svc.list_settlements(db, agent.id)
    ]
    settle_table = render_table(["结算周期", "期间收益", "比例", "应得金额", "状态", "结算时间", "备注"],
                                settle_rows)
    body = (f'<h1 style="color:#111827;">我的账单</h1>{_agent_overview(db, agent)}'
            f'<h2 style="color:#111827;font-size:16px;">结算单</h2>{settle_table}'
            f'<h2 style="color:#111827;font-size:16px;margin-top:28px;">最近30天每日收益</h2>'
            f'<div style="font-size:12px;color:#6b7280;margin-bottom:8px;">'
            f'当天数据实时变化，以结算单金额为准。</div>{daily_table}')
    return HTMLResponse(content=render_page("agent-bills", body, admin))
