"""
后台：提现补贴活动配置
- /admin/subsidy                 活动开关、结束时间、单笔上限、档位列表
- /admin/subsidy/activity        保存活动设置
- /admin/subsidy/tiers/{id|new}  保存/新增档位
"""
import html
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import crud, models, subsidy_service
from app.database import get_db
from app.routers.admin import render_page, verify_admin

router = APIRouter(prefix="/admin/subsidy", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;"
LABEL = "display:inline-block;margin-right:16px;margin-bottom:10px;color:#374151;font-size:14px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:7px 18px;border-radius:6px;font-size:13px;cursor:pointer;"

STATUS_LABELS = {
    "none": ("未开启（App 不显示补贴模块）", "#6b7280"),
    "active": ("进行中", "#16a34a"),
    "ended": ("已结束（App 显示活动已结束）", "#dc2626"),
}


def _redirect(msg: str = "", error: str = "") -> RedirectResponse:
    qs = ""
    if error:
        qs = "?error=" + quote(error)
    elif msg:
        qs = "?msg=" + quote(msg)
    return RedirectResponse(url="/admin/subsidy" + qs, status_code=303)


def _tier_form(tier, rate: int, limit_fen: int) -> str:
    is_new = tier is None
    action = "/admin/subsidy/tiers/new" if is_new else f"/admin/subsidy/tiers/{tier.id}"
    title = "➕ 新增档位" if is_new else f"档位 #{tier.id}"
    withdraw_yuan = "" if is_new else f"{tier.withdraw_fen / 100:.2f}"
    percent = "" if is_new else tier.percent
    per_user_limit = 1 if is_new else tier.per_user_limit
    sort_order = 0 if is_new else tier.sort_order
    enabled = True if is_new else tier.enabled

    info = ""
    if not is_new:
        subsidy = subsidy_service.calc_subsidy_fen(tier)
        arrive = tier.withdraw_fen + subsidy
        coins = subsidy_service.calc_coin_amount(tier, rate)
        over = (' <b style="color:#dc2626;">⚠️ 超出单笔上限，用户无法提交</b>' if arrive > limit_fen else "")
        state = "" if tier.enabled else ' <b style="color:#9ca3af;">（已停用）</b>'
        info = (f'<div style="color:#6b7280;font-size:13px;margin-bottom:10px;">'
                f'实际到账 {arrive / 100:.2f} 元（补贴 {subsidy / 100:.2f} 元），扣除 {coins:,} 金币{over}{state}</div>')

    return f"""
    <div style="border-top:1px solid #f3f4f6;padding-top:14px;margin-top:14px;">
        <div style="font-weight:600;color:#111827;margin-bottom:8px;">{title}</div>
        {info}
        <form method="post" action="{action}">
            <label style="{LABEL}">提现金额(元)
                <input name="withdraw_yuan" value="{withdraw_yuan}" required style="{INPUT}width:90px;"></label>
            <label style="{LABEL}">补贴比例(%)
                <input name="percent" type="number" value="{percent}" required style="{INPUT}width:70px;"></label>
            <label style="{LABEL}">每人限几次(0=不限)
                <input name="per_user_limit" type="number" value="{per_user_limit}" required style="{INPUT}width:70px;"></label>
            <label style="{LABEL}">排序
                <input name="sort_order" type="number" value="{sort_order}" style="{INPUT}width:60px;"></label>
            <label style="{LABEL}">状态
                <select name="enabled" style="{INPUT}">
                    <option value="true" {"selected" if enabled else ""}>启用</option>
                    <option value="false" {"" if enabled else "selected"}>停用</option>
                </select></label>
            <button type="submit" style="{BTN}">{"新增" if is_new else "保存"}</button>
        </form>
    </div>
    """


@router.get("", response_class=HTMLResponse)
def show_subsidy(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    enabled = crud.get_setting(db, "subsidy_enabled", "false").strip().lower() == "true"
    end_raw = crud.get_setting(db, "subsidy_end_at", "").strip()
    end_input = end_raw.replace(" ", "T")[:16]
    limit_yuan = crud.get_setting(db, "wxpay_single_limit_yuan", "50")
    limit_fen = subsidy_service.single_limit_fen(db)
    rate = subsidy_service.coins_per_yuan(db)

    status, _ = subsidy_service.get_status(db)
    status_text, status_color = STATUS_LABELS[status]

    tiers = db.query(models.SubsidyTier).order_by(
        models.SubsidyTier.sort_order, models.SubsidyTier.id
    ).all()
    tiers_html = "".join(_tier_form(t, rate, limit_fen) for t in tiers) + _tier_form(None, rate, limit_fen)

    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    body = f"""
        <h1 style="color:#111827;">提现补贴活动</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            用户在邀请页选档位提现。审核通过（首次发起转账）时活动仍在进行，实际到账 = 提现金额 + 补贴；
            活动结束后才审核的只打提现金额，补贴不发。建议在活动结束前把补贴提现审完。<br>
            档位不能删除，不用了改成"停用"。补贴从运营账户出，注意设置每人限次。
        </p>
        {banner}
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">活动设置
                <span style="font-size:14px;color:{status_color};margin-left:8px;">当前：{status_text}</span></h2>
            <form method="post" action="/admin/subsidy/activity">
                <label style="{LABEL}">活动开关
                    <select name="enabled" style="{INPUT}">
                        <option value="true" {"selected" if enabled else ""}>开启</option>
                        <option value="false" {"" if enabled else "selected"}>关闭</option>
                    </select></label>
                <label style="{LABEL}">结束时间
                    <input type="datetime-local" name="end_at" value="{end_input}" style="{INPUT}"></label>
                <label style="{LABEL}">微信单笔上限(元)
                    <input name="single_limit_yuan" value="{html.escape(limit_yuan)}" required style="{INPUT}width:80px;"></label>
                <button type="submit" style="{BTN}">保存活动设置</button>
            </form>
            <div style="color:#9ca3af;font-size:13px;">单笔上限要和商户平台"商家转账 → 转账额度 → 单笔转账额度"保持一致。
                当前汇率：{rate:,} 金币 = 1 元。</div>
        </div>
        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">补贴档位</h2>
            {tiers_html}
        </div>
    """
    return HTMLResponse(content=render_page("subsidy", body))


@router.post("/activity")
def save_activity(
    enabled: str = Form("false"),
    end_at: str = Form(""),
    single_limit_yuan: str = Form("50"),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    end_at = end_at.strip()
    if end_at:
        try:
            datetime.fromisoformat(end_at)
        except ValueError:
            return _redirect(error="结束时间格式不对")
    if enabled == "true" and not end_at:
        return _redirect(error="开启活动前请先设置结束时间")
    try:
        limit = float(single_limit_yuan)
        if limit <= 0:
            raise ValueError
    except ValueError:
        return _redirect(error="单笔上限必须是大于0的数字")

    crud.set_setting(db, "subsidy_enabled", "true" if enabled == "true" else "false")
    crud.set_setting(db, "subsidy_end_at", end_at)
    crud.set_setting(db, "wxpay_single_limit_yuan", f"{limit:g}")
    return _redirect(msg="活动设置已保存")


@router.post("/tiers/{tier_id}")
def save_tier(
    tier_id: str,
    withdraw_yuan: str = Form(...),
    percent: int = Form(...),
    per_user_limit: int = Form(...),
    sort_order: int = Form(0),
    enabled: str = Form("true"),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    try:
        withdraw_fen = int(round(float(withdraw_yuan) * 100))
    except ValueError:
        return _redirect(error="提现金额格式不对")
    if withdraw_fen < 10:
        return _redirect(error="提现金额不能低于 0.1 元")
    if percent < 0 or percent > 500:
        return _redirect(error="补贴比例要在 0 到 500 之间")
    if per_user_limit < 0:
        return _redirect(error="每人限次不能是负数")

    arrive = withdraw_fen + withdraw_fen * percent // 100
    limit_fen = subsidy_service.single_limit_fen(db)
    if arrive > limit_fen:
        return _redirect(error=f"实际到账 {arrive / 100:.2f} 元超出单笔上限 {limit_fen / 100:.2f} 元，"
                               f"请降低金额或比例，或先去商户平台提额")

    if tier_id == "new":
        tier = models.SubsidyTier()
        db.add(tier)
    else:
        try:
            tier = db.query(models.SubsidyTier).filter(models.SubsidyTier.id == int(tier_id)).first()
        except ValueError:
            tier = None
        if tier is None:
            return _redirect(error="档位不存在")

    tier.withdraw_fen = withdraw_fen
    tier.percent = percent
    tier.per_user_limit = per_user_limit
    tier.sort_order = sort_order
    tier.enabled = enabled == "true"
    db.commit()
    return _redirect(msg="档位已保存")