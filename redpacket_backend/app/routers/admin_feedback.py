"""
后台：用户意见反馈
- /admin/feedback           列表，按状态筛选、分页
- /admin/feedback/{id}      详情，写回复、标记已处理
"""
import html
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.feedback_models import STATUS_COLORS, STATUS_LABELS, Feedback, FeedbackStatus
from app.routers.admin import (
    PAGE_SIZE, render_page, render_pagination, render_table, stat_card, verify_admin,
)

router = APIRouter(prefix="/admin/feedback", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:8px 11px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:14px;cursor:pointer;"


def _redirect(url: str, msg: str = "", error: str = "") -> RedirectResponse:
    if error:
        url += ("&" if "?" in url else "?") + "error=" + quote(error)
    elif msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url=url, status_code=303)


def _banner(msg: str, error: str) -> str:
    if error:
        return (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    if msg:
        return (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')
    return ""


def _status_badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status)
    color = STATUS_COLORS.get(status, "#6b7280")
    return f'<span style="color:{color};font-weight:600;">{label}</span>'


@router.get("", response_class=HTMLResponse)
def show_feedback_list(
    page: int = Query(1, ge=1),
    status_filter: str = Query(None, alias="status"),
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    counts = dict(
        db.query(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status).all()
    )
    total = sum(counts.values())

    query = db.query(Feedback)
    if status_filter in STATUS_LABELS:
        query = query.filter(Feedback.status == status_filter)

    rows_db = (
        query.order_by(Feedback.id.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
        .all()
    )
    has_next = len(rows_db) > PAGE_SIZE
    rows_db = rows_db[:PAGE_SIZE]

    rows = []
    for f in rows_db:
        preview = (f.content or "").replace("\n", " ")
        if len(preview) > 30:
            preview = preview[:30] + "…"
        contact = f.phone or f.email or "-"
        rows.append([
            str(f.id),
            str(f.user_id),
            html.escape(f.nickname or "-"),
            html.escape(preview),
            html.escape(contact),
            _status_badge(f.status),
            f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else "-",
            f'<a href="/admin/feedback/{f.id}" style="color:#2563eb;">查看详情</a>',
        ])

    table_html = render_table(
        ["ID", "用户ID", "昵称", "内容", "联系方式", "状态", "提交时间", "操作"], rows
    )
    extra_qs = f"&status={status_filter}" if status_filter else ""
    pagination_html = render_pagination("/admin/feedback", page, has_next, extra_qs)

    def tab(key, label):
        active = (status_filter == key) or (key is None and not status_filter)
        style = ("color:#2563eb;font-weight:700;" if active else "color:#6b7280;")
        href = "/admin/feedback" if key is None else f"/admin/feedback?status={key}"
        count = total if key is None else counts.get(key, 0)
        return f'<a href="{href}" style="margin-right:18px;text-decoration:none;{style}">{label}({count})</a>'

    tabs = "".join([
        tab(None, "全部"),
        tab(FeedbackStatus.PENDING, "待处理"),
        tab(FeedbackStatus.REPLIED, "已回复"),
        tab(FeedbackStatus.CLOSED, "已关闭"),
    ])

    body = f"""
        <h1 style="color:#111827;">用户意见反馈</h1>
        <div style="display:flex;gap:16px;margin-bottom:20px;">
            {stat_card("反馈总数", str(total))}
            {stat_card("待处理", str(counts.get(FeedbackStatus.PENDING, 0)))}
            {stat_card("已回复", str(counts.get(FeedbackStatus.REPLIED, 0)))}
        </div>
        {_banner(msg, error)}
        <div style="margin-bottom:14px;font-size:14px;">{tabs}</div>
        {table_html}
        {pagination_html}
    """
    return HTMLResponse(content=render_page("feedback", body))


@router.get("/{feedback_id}", response_class=HTMLResponse)
def show_feedback_detail(
    feedback_id: int,
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    f = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if f is None:
        raise HTTPException(status_code=404, detail="这条反馈不存在")

    contact_rows = ""
    if f.phone:
        contact_rows += f'<div style="margin-bottom:6px;">手机号：<b>{html.escape(f.phone)}</b></div>'
    if f.email:
        contact_rows += f'<div style="margin-bottom:6px;">邮箱：<b>{html.escape(f.email)}</b></div>'
    if not contact_rows:
        contact_rows = '<div style="color:#9ca3af;">未留联系方式</div>'

    replied_info = ""
    if f.replied_at:
        replied_info = (f'<div style="color:#9ca3af;font-size:13px;margin-top:8px;">'
                        f'处理时间：{f.replied_at.strftime("%Y-%m-%d %H:%M")}</div>')

    body = f"""
        <h1 style="color:#111827;">反馈详情 #{f.id}</h1>
        <p style="margin-bottom:16px;">
            <a href="/admin/feedback" style="color:#2563eb;">← 返回列表</a>
        </p>
        {_banner(msg, error)}

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">提交人</h2>
            <div style="margin-bottom:6px;">用户ID：<b>{f.user_id}</b>
                <a href="/admin/ad-logs?user_id={f.user_id}" style="color:#2563eb;margin-left:10px;font-size:13px;">查看该用户广告流水</a>
            </div>
            <div style="margin-bottom:6px;">提交时的昵称：<b>{html.escape(f.nickname or "-")}</b></div>
            {contact_rows}
            <div style="color:#9ca3af;font-size:13px;margin-top:8px;">
                提交时间：{f.created_at.strftime("%Y-%m-%d %H:%M:%S") if f.created_at else "-"}
            </div>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">反馈内容</h2>
            <div style="white-space:pre-wrap;line-height:1.8;color:#374151;font-size:15px;">{html.escape(f.content or "")}</div>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">处理</h2>
            <div style="margin-bottom:12px;">当前状态：{_status_badge(f.status)}</div>
            <form method="post" action="/admin/feedback/{f.id}/reply">
                <label style="display:block;color:#374151;font-size:14px;margin-bottom:6px;">
                    回复内容（用户在App「我的反馈」里能看到）</label>
                <textarea name="reply" rows="6"
                          style="{INPUT}width:100%;font-family:inherit;line-height:1.7;">{html.escape(f.reply or "")}</textarea>
                <div style="margin-top:12px;">
                    <button type="submit" name="action" value="reply" style="{BTN}">保存回复并标记已回复</button>
                    <button type="submit" name="action" value="close" style="{BTN}background:#6b7280;margin-left:8px;">标记已关闭</button>
                    <button type="submit" name="action" value="reopen" style="{BTN}background:#f59e0b;margin-left:8px;">退回待处理</button>
                </div>
            </form>
            {replied_info}
        </div>
    """
    return HTMLResponse(content=render_page("feedback", body))


@router.post("/{feedback_id}/reply")
def reply_feedback(
    feedback_id: int,
    reply: str = Form(""),
    action: str = Form("reply"),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    f = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if f is None:
        raise HTTPException(status_code=404, detail="这条反馈不存在")

    url = f"/admin/feedback/{feedback_id}"
    reply = (reply or "").strip()

    if action == "close":
        f.status = FeedbackStatus.CLOSED
        f.reply = reply or f.reply
        f.replied_at = datetime.now()
        db.commit()
        return _redirect(url, msg="已标记为关闭")

    if action == "reopen":
        f.status = FeedbackStatus.PENDING
        f.replied_at = None
        db.commit()
        return _redirect(url, msg="已退回待处理")

    # action == reply
    if not reply:
        return _redirect(url, error="回复内容不能为空")
    f.reply = reply
    f.status = FeedbackStatus.REPLIED
    f.replied_at = datetime.now()
    db.commit()
    return _redirect(url, msg="回复已保存，用户在App里能看到了")
