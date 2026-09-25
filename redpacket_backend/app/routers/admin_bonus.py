"""
后台：福利活动配置
- /admin/bonus  开关、每日看广告次数N、奖励金币M、防刷间隔、提示文案
"""
import html
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.bonus_models import BonusActivityProgress
from app.database import get_db
from app.routers.admin import render_page, verify_admin
from app.routers.bonus import DEFAULT_TIPS, get_config

router = APIRouter(prefix="/admin/bonus", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;"
LABEL = "display:inline-block;margin-right:16px;margin-bottom:12px;color:#374151;font-size:14px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:7px 18px;border-radius:6px;font-size:13px;cursor:pointer;"


def _redirect(msg: str = "", error: str = "") -> RedirectResponse:
    qs = ""
    if error:
        qs = "?error=" + quote(error)
    elif msg:
        qs = "?msg=" + quote(msg)
    return RedirectResponse(url="/admin/bonus" + qs, status_code=303)


@router.get("", response_class=HTMLResponse)
def show_bonus(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    cfg = get_config(db)
    today = date.today()

    joined = (
        db.query(BonusActivityProgress)
        .filter(BonusActivityProgress.stat_date == today)
        .count()
    )
    finished = (
        db.query(BonusActivityProgress)
        .filter(
            BonusActivityProgress.stat_date == today,
            BonusActivityProgress.is_claimed == True,  # noqa: E712
        )
        .count()
    )

    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    body = f"""
        <h1 style="color:#111827;">福利活动配置</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            用户在福利活动页每看完一个激励视频计一次数，看满 N 次服务端当场发 M 金币。<br>
            进度按自然日算，零点自动清零，不需要定时任务。改完即时生效，不用重启服务。
        </p>
        {banner}

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">今日情况（{today}）</h2>
            <p style="color:#374151;font-size:15px;">
                参与人数 <b>{joined}</b> 人，完成人数 <b>{finished}</b> 人
            </p>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">基本设置</h2>
            <form method="post" action="/admin/bonus/save">
                <label style="{LABEL}">活动开关
                    <select name="enabled" style="{INPUT}">
                        <option value="true" {"selected" if cfg.is_enabled else ""}>开启</option>
                        <option value="false" {"" if cfg.is_enabled else "selected"}>关闭</option>
                    </select></label>
                <label style="{LABEL}">每日需看广告次数
                    <input name="target_count" type="number" value="{cfg.target_count}" required
                           style="{INPUT}width:100px;"></label>
                <label style="{LABEL}">完成奖励金币
                    <input name="reward_coin" type="number" value="{cfg.reward_coin}" required
                           style="{INPUT}width:120px;"></label>
                <label style="{LABEL}">两次计数最短间隔(秒)
                    <input name="min_interval_seconds" type="number" value="{cfg.min_interval_seconds}" required
                           style="{INPUT}width:90px;"></label>
                <div style="color:#9ca3af;font-size:13px;margin-bottom:14px;">
                    关闭活动后，App 福利页那张卡片会直接隐藏。间隔填 0 表示不限制，
                    但这个接口一次给 {cfg.reward_coin:,} 金币，建议留 10 秒防脚本。
                </div>
                <label style="display:block;color:#374151;font-size:14px;margin-bottom:6px;">
                    温馨提示文案（显示在活动页底部，留空用默认）</label>
                <textarea name="tips_text" rows="6"
                          style="{INPUT}width:100%;font-family:inherit;line-height:1.7;">{html.escape(cfg.tips_text or DEFAULT_TIPS)}</textarea>
                <button type="submit" style="{BTN}margin-top:12px;">保存设置</button>
            </form>
        </div>
    """
    return HTMLResponse(content=render_page("bonus", body, admin))


@router.post("/save")
def save_bonus(
    enabled: str = Form("true"),
    target_count: int = Form(...),
    reward_coin: int = Form(...),
    min_interval_seconds: int = Form(0),
    tips_text: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    if target_count < 1:
        return _redirect(error="每日需看广告次数至少是 1")
    if reward_coin < 1:
        return _redirect(error="奖励金币至少是 1")
    if min_interval_seconds < 0:
        return _redirect(error="间隔秒数不能是负数")

    cfg = get_config(db)
    cfg.is_enabled = enabled == "true"
    cfg.target_count = target_count
    cfg.reward_coin = reward_coin
    cfg.min_interval_seconds = min_interval_seconds
    cfg.tips_text = tips_text.strip()
    db.commit()
    return _redirect(msg="福利活动设置已保存")
