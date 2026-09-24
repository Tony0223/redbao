"""
后台：公告与协议内容
- /admin/content  平台公告、隐私政策、用户协议，App 端对应页面直接读这里的内容

隐私政策不能留空。华为、小米这些应用市场审核都查，空白页大概率被打回，
已上架的也可能被要求整改。
"""
import html
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.routers.admin import render_page, verify_admin

router = APIRouter(prefix="/admin/content", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:7px 18px;border-radius:6px;font-size:13px;cursor:pointer;"

# 页面key -> (标题, 设置项key, 给运营看的提示)
PAGES = [
    ("平台公告", "notice_content", "App「我的 → 平台公告」显示这段内容，留空则显示“暂无公告”"),
    ("隐私政策", "privacy_content", "App「我的 → 隐私协议」和设置页都会读这段。上架审核必查，不要留空"),
    ("用户协议", "agreement_content", "App「我的设置 → 用户协议」显示这段内容"),
]


def _redirect(msg: str = "", error: str = "") -> RedirectResponse:
    qs = ""
    if error:
        qs = "?error=" + quote(error)
    elif msg:
        qs = "?msg=" + quote(msg)
    return RedirectResponse(url="/admin/content" + qs, status_code=303)


@router.get("", response_class=HTMLResponse)
def show_content(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    cards = ""
    for title, key, hint in PAGES:
        value = crud.get_setting(db, key, "")
        empty_warn = ""
        if not value and key == "privacy_content":
            empty_warn = ('<div style="color:#b91c1c;font-size:13px;margin-bottom:8px;">'
                          '⚠ 当前为空，应用市场审核会因为隐私政策缺失打回</div>')
        cards += f"""
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">{title}</h2>
            <p style="color:#9ca3af;font-size:13px;margin-top:-6px;">{hint}</p>
            {empty_warn}
            <form method="post" action="/admin/content/save">
                <input type="hidden" name="key" value="{key}">
                <textarea name="content" rows="14"
                          style="{INPUT}width:100%;font-family:inherit;line-height:1.8;">{html.escape(value)}</textarea>
                <button type="submit" style="{BTN}margin-top:12px;">保存{title}</button>
            </form>
        </div>
        """

    body = f"""
        <h1 style="color:#111827;">公告与协议</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            改完即时生效，用户重新进入对应页面就能看到新内容，不用发版。<br>
            纯文本即可，换行会原样保留。
        </p>
        {banner}
        {cards}
    """
    return HTMLResponse(content=render_page("content", body))


@router.post("/save")
def save_content(
    key: str = Form(...),
    content: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    valid_keys = {k for _, k, _ in PAGES}
    if key not in valid_keys:
        return _redirect(error="未知的页面类型")
    crud.set_setting(db, key, content.strip())
    title = next(t for t, k, _ in PAGES if k == key)
    return _redirect(msg=f"{title}已保存")
