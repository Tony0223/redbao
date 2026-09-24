"""
后台：每日打卡配置
- /admin/punch  开关、时间段、底池、注入区间、规则文案、手动开奖
"""
import html
from datetime import date, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import crud, models, punch_service
from app.database import get_db
from app.routers.admin import render_page, verify_admin

router = APIRouter(prefix="/admin/punch", tags=["admin"])

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
    return RedirectResponse(url="/admin/punch" + qs, status_code=303)


@router.get("", response_class=HTMLResponse)
def show_punch(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    s = punch_service.get_settings(db)
    today = date.today()
    pool = db.query(models.PunchPool).filter(models.PunchPool.punch_date == today).first()

    pool_html = "今天还没有人打卡"
    if pool:
        total = pool.base_coins + pool.injected_coins
        state = "已开奖" if pool.published else "未开奖"
        pool_html = (f"打卡人数 <b>{pool.punch_count}</b> 人，"
                     f"奖池 <b>{total:,}</b> 金币"
                     f"（底池 {pool.base_coins:,} + 注入 {pool.injected_coins:,}），"
                     f"状态：<b>{state}</b>")

    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    body = f"""
        <h1 style="color:#111827;">每日打卡配置</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            用户每天在时间段内打卡（需看完激励视频），按先后记名次。
            到公布时间自动开奖：前120名按 20%/15%/10%/55% 四档瓜分奖池，档内按累计看广告次数分配。<br>
            奖池 = 固定底池 + 每人打卡随机注入的金币。两项都可以设 0 只用其中一种。
        </p>
        {banner}
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">今日情况（{today}）</h2>
            <p style="color:#374151;font-size:15px;">{pool_html}</p>
            <form method="post" action="/admin/punch/publish" style="display:inline;"
                  onsubmit="return confirm('确认现在开奖？金币会立刻发给前120名用户');">
                <button type="submit" style="{BTN}background:#16a34a;">手动开奖</button>
            </form>
            <span style="color:#9ca3af;font-size:13px;margin-left:10px;">
                正常情况下 {s['publish'].strftime('%H:%M')} 会自动开奖，这里是应急用的
            </span>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">基本设置</h2>
            <form method="post" action="/admin/punch/save">
                <label style="{LABEL}">活动开关
                    <select name="enabled" style="{INPUT}">
                        <option value="true" {"selected" if s['enabled'] else ""}>开启</option>
                        <option value="false" {"" if s['enabled'] else "selected"}>关闭</option>
                    </select></label>
                <label style="{LABEL}">打卡开始
                    <input name="start_time" value="{s['start'].strftime('%H:%M:%S')}" required style="{INPUT}width:110px;"></label>
                <label style="{LABEL}">打卡结束
                    <input name="end_time" value="{s['end'].strftime('%H:%M:%S')}" required style="{INPUT}width:110px;"></label>
                <label style="{LABEL}">开奖时间
                    <input name="publish_time" value="{s['publish'].strftime('%H:%M:%S')}" required style="{INPUT}width:110px;"></label>
                <br>
                <label style="{LABEL}">固定底池(金币)
                    <input name="base_pool" type="number" value="{s['base_pool']}" required style="{INPUT}width:120px;"></label>
                <label style="{LABEL}">打卡注入下限
                    <input name="inject_min" type="number" value="{s['inject_min']}" required style="{INPUT}width:110px;"></label>
                <label style="{LABEL}">打卡注入上限
                    <input name="inject_max" type="number" value="{s['inject_max']}" required style="{INPUT}width:110px;"></label>
                <div style="color:#9ca3af;font-size:13px;margin-bottom:14px;">
                    注入上限设 0 表示不注入，奖池就只有固定底池。
                </div>
                <label style="display:block;color:#374151;font-size:14px;margin-bottom:6px;">规则文案（App规则弹窗显示，留空用默认）</label>
                <textarea name="rules" rows="12" style="{INPUT}width:100%;font-family:inherit;line-height:1.7;">{html.escape(s['rules'])}</textarea>
                <button type="submit" style="{BTN}margin-top:12px;">保存设置</button>
            </form>
        </div>
    """
    return HTMLResponse(content=render_page("punch", body))


@router.post("/save")
def save_punch(
    enabled: str = Form("true"),
    start_time: str = Form(...),
    end_time: str = Form(...),
    publish_time: str = Form(...),
    base_pool: int = Form(...),
    inject_min: int = Form(...),
    inject_max: int = Form(...),
    rules: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    for label, value in (("打卡开始", start_time), ("打卡结束", end_time), ("开奖", publish_time)):
        try:
            datetime.strptime(value.strip(), "%H:%M:%S")
        except ValueError:
            return _redirect(error=f"{label}时间格式不对，要像 07:00:00 这样")

    if base_pool < 0 or inject_min < 0 or inject_max < 0:
        return _redirect(error="金币数不能是负数")
    if inject_max > 0 and inject_min > inject_max:
        return _redirect(error="注入下限不能大于上限")

    crud.set_setting(db, "punch_enabled", "true" if enabled == "true" else "false")
    crud.set_setting(db, "punch_start_time", start_time.strip())
    crud.set_setting(db, "punch_end_time", end_time.strip())
    crud.set_setting(db, "punch_publish_time", publish_time.strip())
    crud.set_setting(db, "punch_base_pool", str(base_pool))
    crud.set_setting(db, "punch_inject_min", str(inject_min))
    crud.set_setting(db, "punch_inject_max", str(inject_max))
    crud.set_setting(db, "punch_rules", rules.strip())
    return _redirect(msg="打卡设置已保存")


@router.post("/publish")
def publish_now(
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    result = punch_service.publish(db, date.today())
    if result["ok"]:
        return _redirect(msg=result["message"] + f"（奖池 {result.get('total', 0):,} 金币，"
                                                 f"{result.get('winners', 0)} 人中奖）")
    return _redirect(error=result["message"])