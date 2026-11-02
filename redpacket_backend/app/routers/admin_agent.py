"""
代理商后台页面。

管理端(超管，或被分配了“代理商管理”菜单的管理员)：
- /admin/agents                    代理列表 + 新建代理(同时创建代理登录账号)
- /admin/agents/{id}/update        修改名称/比例/联系方式/启停/重置密码
- /admin/agents/settlements        结算单：按代理+时间段生成，线下打款后标记已结算

代理商账号(只看自己的)：
- /admin/agent-users               我的用户 + 收益概览
- /admin/agent-bills               我的账单：每日收益明细 + 结算单

- /admin/agents/gromore             穿山甲真实收益：配置 GroMore 数据API、拉取每日收益API、查看校正系数

收益口径：App 每次广告展示上报 eCPM，单次收益 = eCPM / 1000 (分)；
再按穿山甲每天的真实收益(收益API)校正：系数 = min(1, 真实收益 / 全体上报收益)。
还没拉到真实收益的日期(如今天)显示上报值，标“预估”；结算单只按校正后的金额生成。
"""
import html
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app import agent_service as svc
from app import gromore_service as gm
from app.agent_models import SETTLEMENT_STATUS_LABELS, SettlementStatus
from app import crud
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


def _month_dates(today: date):
    """本月 1 号~今天，上月 1 号~上月最后一天"""
    m_start = today.replace(day=1)
    lm_end = m_start - timedelta(days=1)
    return (m_start, today), (lm_end.replace(day=1), lm_end)


def _est_tag(est) -> str:
    return ('<span class="ag-est" title="包含还没按穿山甲真实收益校正的预估部分">含预估</span>'
            if est and est > 0 else "")


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
    (m_start, m_end), (lm_start, lm_end) = _month_dates(date.today())
    rows = []
    dialogs = []
    for a in svc.list_agents(db):
        login = "—"
        if a.admin_user_id:
            from app import crud
            au = crud.get_admin_user_by_id(db, a.admin_user_id)
            login = html.escape(au.username) if au else "—"
        month_rev, month_est, _ = svc.calibrated_revenue(db, a.id, m_start, m_end)
        last_rev, last_est, _ = svc.calibrated_revenue(db, a.id, lm_start, lm_end)
        link = _invite_link(request, a.invite_code)
        link_js = html.escape(json.dumps(link), quote=True)
        status = ('<span class="ag-tag ag-on">启用</span>' if a.enabled
                  else '<span class="ag-tag ag-off">停用</span>')
        invite_cell = (
            f'<b style="letter-spacing:1px;">{a.invite_code}</b>'
            f'<div style="margin-top:4px;">'
            f'<button type="button" class="ag-link" onclick="agCopy({link_js})">复制链接</button>'
            f'<span style="color:#d1d5db;margin:0 6px;">|</span>'
            f'<a class="ag-link" href="/admin/agents/{a.id}/qrcode.png?download=1">下载二维码</a></div>'
        )
        edit_btn = (f'<button type="button" class="ag-btn ag-btn-o" '
                    f'onclick="document.getElementById(\'dlg-{a.id}\').showModal()">编辑</button> '
                    f'<a class="ag-btn ag-btn-o" style="text-decoration:none;display:inline-block;" '
                    f'href="/admin/agents/{a.id}/daily">明细</a>')
        dialogs.append(f"""
        <dialog class="ag-dlg" id="dlg-{a.id}">
          <form method="post" action="/admin/agents/{a.id}/update">
            <div class="hd">编辑代理 · {html.escape(a.name)}</div>
            <div class="bd">
              <label class="k">代理名称</label>
              <input class="ag-in" name="name" value="{html.escape(a.name)}" required />
              <label class="k">分成比例</label>
              <div class="ag-suffix"><input class="ag-in" name="share_ratio" value="{a.share_ratio}" required /><span>%</span></div>
              <label class="k">联系方式</label>
              <input class="ag-in" name="contact" value="{html.escape(a.contact or '')}" placeholder="选填" />
              <label class="k">备注</label>
              <input class="ag-in" name="remark" value="{html.escape(a.remark or '')}" placeholder="选填" />
              <label class="k">状态</label>
              <label class="ag-check"><input type="checkbox" name="enabled" {"checked" if a.enabled else ""}/>
                启用<span class="ag-hint">停用后代理无法登录，新用户不再归属</span></label>
              <label class="k">登录账号</label>
              <div style="font-size:14px;color:#111827;">{login}</div>
              <label class="k">重置密码</label>
              <input class="ag-in" name="password" placeholder="留空则不修改" autocomplete="new-password" />
            </div>
            <div class="ft">
              <button type="button" class="ag-btn ag-btn-g" onclick="this.closest('dialog').close()">取消</button>
              <button type="submit" class="ag-btn ag-btn-p">保存</button>
            </div>
          </form>
        </dialog>""")
        rows.append([
            a.id,
            f'<span style="font-weight:600;">{html.escape(a.name)}</span>',
            invite_cell,
            f"{a.share_ratio}%",
            svc.count_agent_users(db, a.id),
            f"¥{svc.fen_to_yuan(month_rev)}{_est_tag(month_est)}",
            f"¥{svc.fen_to_yuan(svc.share_of(a, month_rev))}{_est_tag(month_est)}",
            f"¥{svc.fen_to_yuan(svc.share_of(a, last_rev))}{_est_tag(last_est)}",
            f"¥{svc.fen_to_yuan(svc.pending_share_fen(db, a.id))}",
            login,
            status,
            edit_btn,
        ])
    table = render_table(
        ["ID", "名称", "专属邀请码", "比例", "名下用户", "本月收益", "本月应分", "上月应分", "待打款",
         "登录账号", "状态", "操作"],
        rows,
    )
    create_form = """
    <div class="ag-card">
      <h2 style="margin:0 0 16px;color:#111827;font-size:16px;">新建代理商</h2>
      <form method="post" action="/admin/agents/create">
        <div class="ag-grid">
          <div><label class="t">代理名称 *</label><input class="ag-in" name="name" required /></div>
          <div><label class="t">分成比例 *</label>
            <div class="ag-suffix"><input class="ag-in" name="share_ratio" placeholder="如 30" required /><span>%</span></div></div>
          <div><label class="t">联系方式</label><input class="ag-in" name="contact" placeholder="选填" /></div>
          <div><label class="t">登录账号 *</label><input class="ag-in" name="username" autocomplete="off" required /></div>
          <div><label class="t">登录密码 *</label><input class="ag-in" name="password" autocomplete="new-password" required /></div>
          <div><label class="t">备注</label><input class="ag-in" name="remark" placeholder="选填" /></div>
        </div>
        <div style="margin-top:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <button type="submit" class="ag-btn ag-btn-s">创建代理</button>
          <span class="ag-hint">创建后自动生成专属邀请码；用户通过该邀请链接注册即归属此代理。</span>
        </div>
      </form>
    </div>
    """
    nav = ('<div style="margin-bottom:16px;display:flex;gap:20px;">'
           '<a href="/admin/agents/settlements" style="color:#2563eb;">→ 代理结算单</a>'
           '<a href="/admin/agents/gromore" style="color:#2563eb;">→ 穿山甲真实收益</a></div>')
    body = (f'{_AGENT_PAGE_ASSETS}<h1 style="color:#111827;">代理商管理</h1>{_tip(msg, bool(ok))}{nav}'
            f'<div style="font-size:13px;color:#6b7280;margin-bottom:12px;">'
            f'收益=名下用户广告展示上报的eCPM累计，按穿山甲每天的真实收益校正(只少不多)；'
            f'应分=收益×比例。“含预估”表示其中有还没拉到穿山甲真实收益的日期(如今天)。</div>'
            f'<div class="ag-tbl">{table}</div>{create_form}{"".join(dialogs)}')
    return HTMLResponse(content=render_page("agents", body, admin))


# 代理商管理页的样式和脚本：表格不换行(放不下横向滚动)、编辑弹窗、复制链接
_AGENT_PAGE_ASSETS = """
<style>
  .ag-tbl { overflow-x:auto; border-radius:12px; }
  .ag-tbl th, .ag-tbl td { white-space:nowrap; }
  .ag-in { width:100%; box-sizing:border-box; padding:9px 11px; border:1px solid #d1d5db;
           border-radius:8px; font-size:14px; color:#111827; background:#fff; }
  .ag-in:focus { outline:none; border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.15); }
  .ag-suffix { display:flex; align-items:center; gap:8px; }
  .ag-suffix span { color:#6b7280; font-size:14px; }
  .ag-btn { border:none; border-radius:8px; padding:8px 18px; font-size:14px; cursor:pointer; }
  .ag-btn-p { background:#2563eb; color:#fff; }
  .ag-btn-s { background:#16a34a; color:#fff; padding:9px 22px; }
  .ag-btn-g { background:#f3f4f6; color:#374151; }
  .ag-btn-o { background:#fff; color:#2563eb; border:1px solid #bfdbfe; padding:5px 14px; font-size:13px; }
  .ag-btn-o:hover { background:#eff6ff; }
  .ag-link { color:#2563eb; font-size:12px; background:none; border:none; padding:0; cursor:pointer;
             text-decoration:none; }
  .ag-link:hover { text-decoration:underline; }
  .ag-tag { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; }
  .ag-on { background:#dcfce7; color:#166534; }
  .ag-off { background:#fee2e2; color:#991b1b; }
  .ag-hint { color:#9ca3af; font-size:12px; margin-left:6px; }
  .ag-est { display:inline-block; margin-left:6px; padding:0 6px; border-radius:4px; font-size:11px;
            background:#fef3c7; color:#92400e; vertical-align:middle; font-weight:400; }
  .ag-card { border:1px solid #e5e7eb; border-radius:12px; padding:22px 24px; margin-top:24px; background:#fff; }
  .ag-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:14px 16px; }
  .ag-grid label.t { display:block; font-size:13px; color:#374151; margin-bottom:6px; }
  .ag-dlg { border:none; border-radius:14px; padding:0; width:460px; max-width:92vw;
            box-shadow:0 24px 60px rgba(0,0,0,.25); }
  .ag-dlg::backdrop { background:rgba(17,24,39,.45); }
  .ag-dlg .hd { padding:18px 24px; border-bottom:1px solid #f3f4f6; font-size:16px; font-weight:600; color:#111827; }
  .ag-dlg .bd { padding:20px 24px; display:grid; grid-template-columns:80px 1fr; gap:14px 14px; align-items:center; }
  .ag-dlg label.k { color:#6b7280; font-size:13px; text-align:right; }
  .ag-dlg .ag-check { font-size:14px; color:#111827; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
  .ag-dlg .ag-check .ag-hint { margin-left:0; width:100%; }
  .ag-dlg .ft { padding:14px 24px; border-top:1px solid #f3f4f6; display:flex; justify-content:flex-end; gap:10px; }
</style>
<script>
  function agCopy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { alert('邀请链接已复制'); },
                                               function () { prompt('请复制下面的邀请链接', text); });
    } else {
      prompt('请复制下面的邀请链接', text);
    }
  }
</script>
"""


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
                      f'标记已结算</button></form>'
                      f'<form method="post" action="/admin/agents/settlements/{s.id}/delete" '
                      f'onsubmit="return confirm(\'确定删除这张待结算单？删除后可重新生成\')" style="margin:6px 0 0;">'
                      f'<button type="submit" style="{BTN_STYLE}background:#dc2626;padding:5px 12px;">'
                      f'删除</button></form>')
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
    # 默认填上个月(每月结一次直接点生成)
    last_start, last_end = svc.prev_month_range(date.today())
    default_start = last_start.date().isoformat()
    default_end = (last_end.date() - timedelta(days=1)).isoformat()
    gen_options = "".join(f'<option value="{a.id}">{html.escape(a.name)}</option>' for a in agents)
    create_form = f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:24px;margin-top:24px;background:#fff;">
      <h2 style="margin-top:0;color:#111827;font-size:16px;">生成结算单</h2>
      <form method="post" action="/admin/agents/settlements/create" style="line-height:2.6;">
        代理 <select name="agent_id" required style="{INPUT_STYLE}">{gen_options}</select>
        开始 <input type="date" name="start" value="{default_start}" required style="{INPUT_STYLE}" />
        结束 <input type="date" name="end" value="{default_end}" required style="{INPUT_STYLE}" />
        <input name="remark" placeholder="备注(选填)" style="{INPUT_STYLE}" />
        <button type="submit" style="{BTN_STYLE}background:#2563eb;">生成</button>
        <div style="font-size:12px;color:#6b7280;">
          按所选时间段(含首尾两天)统计该代理名下用户的广告收益，并按穿山甲每天的真实收益校正(只少不多)，
          再按代理当前比例计算应付金额并冻结；只能结算到昨天，同一代理时间段不能重叠；
          期间内有任何一天还没拉到穿山甲真实收益时不能生成，请先到
          <a href="/admin/agents/gromore" style="color:#2563eb;">穿山甲真实收益</a> 拉取。</div>
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


@router.post("/agents/settlements/{settlement_id}/delete")
def settlements_delete(
    settlement_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    try:
        svc.delete_settlement(db, settlement_id)
    except svc.AgentError as e:
        return _redirect("/admin/agents/settlements", str(e), ok=False)
    return _redirect("/admin/agents/settlements", "已删除，可重新生成")


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

def _ov_card(label: str, value: str, hint: str = "") -> str:
    hint_html = f'<div style="color:#9ca3af;font-size:12px;margin-top:4px;">{hint}</div>' if hint else ""
    return (f'<div style="flex:1 1 200px;min-width:200px;background:#fff;border:1px solid #e5e7eb;'
            f'border-radius:12px;padding:16px 18px;">'
            f'<div style="color:#6b7280;font-size:13px;margin-bottom:6px;">{label}</div>'
            f'<div style="color:#111827;font-size:20px;font-weight:700;">{value}</div>{hint_html}</div>')


def _agent_overview(db: Session, agent) -> str:
    """收益概览(代理也看)。每格：收益 / 预计分成。金额已校正，但代理端不出现“校正/穿山甲”字样，没校正的只提示“含预估”。"""
    today = date.today()
    d_start, d_end = svc.day_range(today)
    yesterday = today - timedelta(days=1)
    (m_start, m_end), (lm_start, lm_end) = _month_dates(today)

    def card(label, result):
        rev, est, _ = result
        hint = f"含预估 ¥{svc.fen_to_yuan(est)}" if est > 0 else ""
        return _ov_card(label, f"¥{svc.fen_to_yuan(rev)} / ¥{svc.fen_to_yuan(svc.share_of(agent, rev))}", hint)

    cards = "".join([
        _ov_card("名下用户", str(svc.count_agent_users(db, agent.id)),
                 f"今日新增 {svc.count_agent_users(db, agent.id, d_start, d_end)}"),
        card("今日收益 / 预计分成", svc.calibrated_revenue(db, agent.id, today, today)),
        card("昨日收益 / 预计分成", svc.calibrated_revenue(db, agent.id, yesterday, yesterday)),
        card("本月收益 / 预计分成", svc.calibrated_revenue(db, agent.id, m_start, m_end)),
        card("上月收益 / 预计分成", svc.calibrated_revenue(db, agent.id, lm_start, lm_end)),
        card("累计收益 / 预计分成", svc.calibrated_total(db, agent.id)),
        _ov_card("待打款", f"¥{svc.fen_to_yuan(svc.pending_share_fen(db, agent.id))}",
                 "已出结算单、还没打款的金额"),
    ])
    return (f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px;">{cards}</div>'
            f'<div style="font-size:12px;color:#9ca3af;margin-bottom:20px;">'
            f'还没出最终数据的日期(如今天)是预估值，最终以结算单金额为准。“预计分成”按当前比例估算。</div>')


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
    table = render_table(["用户ID", "昵称", "注册时间", "累计看广告", "广告展示", "累计贡献收益(预估)"], rows)
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
    body = (f'{_EST_STYLE}<h1 style="color:#111827;">我的用户</h1>{info}{_agent_overview(db, agent)}{table}'
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
        [str(d), shows, f"¥{svc.fen_to_yuan(rev)}",
         ('' if f is not None else '<span class="ag-est" style="margin:0 6px 0 0;">预估</span>')
         + f"¥{svc.fen_to_yuan(svc.share_of(agent, rev))}"]
        for d, shows, _raw, rev, f in svc.calibrated_daily(db, agent.id, 30)
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
            f'标“预估”的是还没出最终数据的日期，最终以结算单金额为准。</div>{daily_table}')
    body = _EST_STYLE + body
    return HTMLResponse(content=render_page("agent-bills", body, admin))


_EST_STYLE = """<style>.ag-est { display:inline-block; margin-left:6px; padding:0 6px; border-radius:4px;
  font-size:11px; background:#fef3c7; color:#92400e; vertical-align:middle; }</style>"""


# ==================== 管理端：穿山甲真实收益 ====================

@router.get("/agents/gromore", response_class=HTMLResponse)
def gromore_page(
    msg: str = "",
    ok: int = 1,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    cfg = gm.get_config(db)
    today = date.today()
    start = today - timedelta(days=44)
    real = gm.list_real(db, start, today)
    reported = svc._daily_reported(db, start, today)
    factors = svc.day_factors(db, start, today)
    rows = []
    d = today
    while d >= start:
        r = real.get(d)
        rep_fen = reported.get(d)
        if r is not None or rep_fen:
            if r is None:
                status = ('<span class="ag-est" style="margin-left:0;">预估</span>' if d == today
                          else '<span style="color:#dc2626;">未拉取</span>')
            else:
                status = '<span style="color:#16a34a;">已校正</span>'
            f = factors.get(d)
            gap = ""
            if r is not None and r.imp_cnt:
                gap = f"{r.api_imp_cnt} / {r.imp_cnt}"
            rows.append([
                str(d),
                f"¥{svc.fen_to_yuan(r.revenue_fen)}" if r is not None else "—",
                f"¥{svc.fen_to_yuan(rep_fen or 0)}",
                f"{f:.4f}" if f is not None else "—",
                gap or "—",
                r.fetched_at.strftime("%m-%d %H:%M") if r is not None and r.fetched_at else "—",
                status,
            ])
        d -= timedelta(days=1)
    table = render_table(
        ["日期", "穿山甲收益API", "全体用户上报收益", "校正系数", "展示API / GroMore展示", "拉取时间", "状态"],
        rows,
    )
    key_ph = "已设置（留空则不修改）" if cfg["security_key"] else "未设置"
    configured = gm.is_configured(cfg)
    last_sync = html.escape(crud.get_setting(db, gm.KEY_LAST_SYNC, "") or "还没有拉取过")
    yesterday = today - timedelta(days=1)
    config_form = f"""
    <div class="ag-card" style="margin-top:0;">
      <h2 style="margin:0 0 6px;color:#111827;font-size:16px;">GroMore 数据API 配置</h2>
      <div class="ag-hint" style="margin:0 0 14px;">
        在穿山甲后台获取 security key、user_id、role_id。若用子账号，主账号需在“角色管理”里给该角色配置“查看全部数据”权限。</div>
      <form method="post" action="/admin/agents/gromore/config">
        <div class="ag-grid">
          <div><label class="t">user_id *</label>
            <input class="ag-in" name="user_id" value="{html.escape(cfg['user_id'])}" required /></div>
          <div><label class="t">role_id *</label>
            <input class="ag-in" name="role_id" value="{html.escape(cfg['role_id'])}" required /></div>
          <div><label class="t">security key *</label>
            <input class="ag-in" type="password" name="security_key" placeholder="{key_ph}" autocomplete="new-password" /></div>
          <div><label class="t">应用ID（选填）</label>
            <input class="ag-in" name="site_ids" value="{html.escape(cfg['site_ids'])}" placeholder="只统计这个App，多个用逗号分隔" /></div>
        </div>
        <div style="margin-top:16px;"><button type="submit" class="ag-btn ag-btn-p">保存配置</button></div>
      </form>
    </div>"""
    sync_form = f"""
    <div class="ag-card">
      <h2 style="margin:0 0 6px;color:#111827;font-size:16px;">拉取真实收益</h2>
      <div class="ag-hint" style="margin:0 0 14px;">
        系统每天 15:20 和 21:20 自动拉取最近 7 天(穿山甲前一天的数据次日 14 点后才完整，三方数据可能事后修正，所以会重拉覆盖)。
        需要补历史数据(比如上个月)时在这里手动拉，一次最多 31 天。</div>
      <form method="post" action="/admin/agents/gromore/sync" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        开始 <input class="ag-in" style="width:auto;" type="date" name="start" value="{(yesterday - timedelta(days=6)).isoformat()}" required />
        结束 <input class="ag-in" style="width:auto;" type="date" name="end" value="{yesterday.isoformat()}" required />
        <button type="submit" class="ag-btn ag-btn-s" {"" if configured else "disabled"}>立即拉取</button>
        {"" if configured else '<span class="ag-hint">先保存上面的配置</span>'}
      </form>
      <div style="margin-top:12px;font-size:12px;color:#6b7280;word-break:break-all;">最近一次：{last_sync}</div>
    </div>"""
    explain = ('<div style="font-size:13px;color:#6b7280;margin:24px 0 10px;line-height:1.8;">'
               '校正系数 = min(1, 穿山甲收益API ÷ 全体用户上报收益)。代理当天收益 = 上报收益 × 系数，'
               '保证分给代理的钱不超过穿山甲实际给的钱。“未拉取”的日期不能生成结算单。'
               '“展示API / GroMore展示”差距很大时，说明有广告网络没授权 Reporting API，真实收益会偏少。</div>')
    body = (f'{_AGENT_PAGE_ASSETS}<h1 style="color:#111827;">穿山甲真实收益</h1>{_tip(msg, bool(ok))}'
            f'<div style="margin-bottom:16px;"><a href="/admin/agents" style="color:#2563eb;">← 返回代理商管理</a></div>'
            f'{config_form}{sync_form}{explain}<div class="ag-tbl">{table}</div>')
    return HTMLResponse(content=render_page("agents", body, admin))


@router.post("/agents/gromore/config")
async def gromore_config(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    form = await request.form()
    try:
        gm.save_config(
            db,
            user_id=(form.get("user_id") or "").strip(),
            role_id=(form.get("role_id") or "").strip(),
            security_key=(form.get("security_key") or "").strip(),
            site_ids=(form.get("site_ids") or "").strip(),
        )
    except gm.GroMoreError as e:
        return _redirect("/admin/agents/gromore", str(e), ok=False)
    return _redirect("/admin/agents/gromore", "配置已保存")


@router.post("/agents/gromore/sync")
async def gromore_sync(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    form = await request.form()
    try:
        start = date.fromisoformat(form.get("start") or "")
        end = date.fromisoformat(form.get("end") or "")
    except ValueError:
        return _redirect("/admin/agents/gromore", "日期格式不对", ok=False)
    try:
        # 拉取要请求穿山甲接口(网络慢时可能几十秒)，放到线程池里跑，
        # 不能直接在 async 函数里同步调用，否则会卡住整个后端，其他页面全部 504
        results = await run_in_threadpool(gm.sync_range, db, start, end)
    except gm.GroMoreError as e:
        return _redirect("/admin/agents/gromore", str(e), ok=False)
    failed = [r for r in results if "失败" in r or "未入库" in r]
    msg = ("拉取完成：" if not failed else "部分日期未成功：") + "；".join(failed or results[-3:])
    return _redirect("/admin/agents/gromore", msg[:600], ok=not failed)


# ==================== 管理端：单个代理最近30天每日收益(含校正) ====================

@router.get("/agents/{agent_id}/daily", response_class=HTMLResponse)
def agent_daily_admin(
    agent_id: int,
    db: Session = Depends(get_db),
    admin=Depends(verify_admin),
):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        return _redirect("/admin/agents", "代理不存在", ok=False)
    rows = []
    for d, shows, raw, rev, f in svc.calibrated_daily(db, agent.id, 30):
        rows.append([
            str(d),
            shows,
            f"¥{svc.fen_to_yuan(raw)}",
            f"{f:.4f}" if f is not None else "—",
            f"¥{svc.fen_to_yuan(rev)}",
            f"¥{svc.fen_to_yuan(svc.share_of(agent, rev))}",
            '<span style="color:#16a34a;">已校正</span>' if f is not None
            else '<span class="ag-est" style="margin-left:0;">预估</span>',
        ])
    table = render_table(["日期", "广告展示次数", "上报收益", "校正系数", "校正后收益", "预计分成", "数据状态"], rows)
    body = (f'{_AGENT_PAGE_ASSETS}<h1 style="color:#111827;">{html.escape(agent.name)} · 最近30天每日收益</h1>'
            f'<div style="margin-bottom:16px;"><a href="/admin/agents" style="color:#2563eb;">← 返回代理商管理</a></div>'
            f'<div style="font-size:13px;color:#6b7280;margin-bottom:12px;">'
            f'分成比例 {agent.share_ratio}%。校正后收益 = 上报收益 × 当天校正系数(见'
            f'<a href="/admin/agents/gromore" style="color:#2563eb;">穿山甲真实收益</a>)；'
            f'“预估”= 当天还没拉到穿山甲真实收益，按上报值算。此页面代理看不到。</div>'
            f'<div class="ag-tbl">{table}</div>')
    return HTMLResponse(content=render_page("agents", body, admin))
