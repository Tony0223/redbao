"""
后台：每日签到配置
- /admin/signin  改每天的金币数、增删周期天数
"""
import html
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import models, signin_service
from app.database import get_db
from app.routers.admin import render_page, verify_admin

router = APIRouter(prefix="/admin/signin", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;width:110px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:7px 18px;border-radius:6px;font-size:13px;cursor:pointer;"


def _redirect(msg: str = "", error: str = "") -> RedirectResponse:
    qs = ""
    if error:
        qs = "?error=" + quote(error)
    elif msg:
        qs = "?msg=" + quote(msg)
    return RedirectResponse(url="/admin/signin" + qs, status_code=303)


@router.get("", response_class=HTMLResponse)
def show_signin(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    cycle = signin_service.get_cycle(db)

    rows_html = ""
    for c in cycle:
        rows_html += f"""
        <div style="display:inline-block;margin:0 14px 14px 0;text-align:center;">
            <div style="color:#6b7280;font-size:13px;margin-bottom:6px;">第{c.day_index}天</div>
            <input name="day_{c.day_index}" type="number" value="{c.coins}" required style="{INPUT}">
        </div>
        """

    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    body = f"""
        <h1 style="color:#111827;">每日签到配置</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            用户每天签到一次（需看完激励视频），按下面配置发金币。连续签到往后推进，
            中途断签从第1天重新开始，签满一轮后也回到第1天。<br>
            改完立刻生效，不用重新发版。
        </p>
        {banner}
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">每天奖励金币（当前{len(cycle)}天一轮）</h2>
            <form method="post" action="/admin/signin/save">
                <div>{rows_html}</div>
                <button type="submit" style="{BTN}">保存</button>
            </form>
        </div>
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">调整周期长度</h2>
            <form method="post" action="/admin/signin/resize" style="display:inline;"
                  onsubmit="return confirm('调整天数会影响正在签到的用户，确认继续？');">
                <label style="color:#374151;font-size:14px;margin-right:10px;">周期天数
                    <input name="days" type="number" value="{len(cycle)}" min="1" max="31" required style="{INPUT}"></label>
                <button type="submit" style="{BTN}">调整</button>
            </form>
            <div style="color:#9ca3af;font-size:13px;margin-top:10px;">
                改大：新增的天数默认补 1000 金币，保存后再改数值。改小：多出来的天数会被删掉。
            </div>
        </div>
    """
    return HTMLResponse(content=render_page("signin", body))


@router.post("/save")
async def save_signin(
    request: __import__("fastapi").Request,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    form = await request.form()
    cycle = signin_service.get_cycle(db)
    for c in cycle:
        key = f"day_{c.day_index}"
        if key not in form:
            continue
        try:
            coins = int(form[key])
        except ValueError:
            return _redirect(error=f"第{c.day_index}天的金币数格式不对")
        if coins < 0:
            return _redirect(error="金币数不能是负数")
        c.coins = coins
        db.add(c)
    db.commit()
    return _redirect(msg="签到配置已保存")


@router.post("/resize")
def resize_cycle(
    days: int = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    if days < 1 or days > 31:
        return _redirect(error="周期天数要在 1 到 31 之间")

    cycle = signin_service.get_cycle(db)
    current = len(cycle)

    if days > current:
        for i in range(current + 1, days + 1):
            db.add(models.SignInConfig(day_index=i, coins=1000))
    elif days < current:
        db.query(models.SignInConfig).filter(
            models.SignInConfig.day_index > days
        ).delete(synchronize_session=False)

    db.commit()
    return _redirect(msg=f"周期已调整为 {days} 天")