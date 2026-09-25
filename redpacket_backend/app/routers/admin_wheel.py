"""
后台：幸运转盘配置
- /admin/wheel                 开关、每日抽奖次数、防刷间隔、规则文案、今日情况
- /admin/wheel/prize           新增/保存一个奖品（格子）
- /admin/wheel/prize/delete    删除一个奖品
"""
import html
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin import render_page, verify_admin
from app.routers.wheel import DEFAULT_RULES, _taken_today, get_config, get_prizes
from app.wheel_models import WheelChance, WheelDrawRecord, WheelPrize

router = APIRouter(prefix="/admin/wheel", tags=["admin"])

CARD = "border:1px solid #e5e7eb;border-radius:12px;padding:20px 24px;margin-bottom:20px;background:#fff;"
INPUT = "padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;"
LABEL = "display:inline-block;margin-right:16px;margin-bottom:12px;color:#374151;font-size:14px;"
BTN = "background:#2563eb;color:#fff;border:none;padding:7px 18px;border-radius:6px;font-size:13px;cursor:pointer;"
TD = "padding:8px 6px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#111827;white-space:nowrap;"
TH = "text-align:left;padding:10px 6px;color:#6b7280;font-size:13px;border-bottom:1px solid #e5e7eb;white-space:nowrap;"
CELL_INPUT = "padding:5px 7px;border:1px solid #d1d5db;border-radius:5px;font-size:13px;"


def _redirect(msg: str = "", error: str = "") -> RedirectResponse:
    qs = ""
    if error:
        qs = "?error=" + quote(error)
    elif msg:
        qs = "?msg=" + quote(msg)
    return RedirectResponse(url="/admin/wheel" + qs, status_code=303)


def _prize_row(p: WheelPrize, chance_pct: float, taken: int) -> str:
    """一行 = 一个格子，行内直接改直接存"""
    return f"""
    <tr>
      <form method="post" action="/admin/wheel/prize">
      <input type="hidden" name="prize_id" value="{p.id}">
      <td style="{TD}"><input name="sort_order" type="number" value="{p.sort_order}" style="{CELL_INPUT}width:50px;"></td>
      <td style="{TD}"><input name="label" value="{html.escape(p.label or '')}" style="{CELL_INPUT}width:110px;"></td>
      <td style="{TD}"><input name="min_coin" type="number" value="{p.min_coin}" style="{CELL_INPUT}width:85px;"></td>
      <td style="{TD}"><input name="max_coin" type="number" value="{p.max_coin}" style="{CELL_INPUT}width:85px;"></td>
      <td style="{TD}"><input name="weight" type="number" value="{p.weight}" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}color:#2563eb;font-weight:700;">{chance_pct:.1f}%</td>
      <td style="{TD}"><input name="daily_limit" type="number" value="{p.daily_limit}" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}"><input name="user_daily_limit" type="number" value="{p.user_daily_limit}" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}color:#dc2626;">{taken}</td>
      <td style="{TD}">
        <select name="enabled" style="{CELL_INPUT}">
          <option value="true" {"selected" if p.is_enabled else ""}>启用</option>
          <option value="false" {"" if p.is_enabled else "selected"}>停用</option>
        </select></td>
      <td style="{TD}">
        <button type="submit" style="{BTN}padding:5px 12px;">保存</button>
      </form>
        <form method="post" action="/admin/wheel/prize/delete" style="display:inline;"
              onsubmit="return confirm('确认删除这个格子？历史抽奖记录不受影响');">
          <input type="hidden" name="prize_id" value="{p.id}">
          <button type="submit" style="{BTN}padding:5px 12px;background:#dc2626;margin-left:4px;">删除</button>
        </form>
      </td>
    </tr>"""


def _new_prize_row(next_order: int) -> str:
    return f"""
    <tr style="background:#f9fafb;">
      <form method="post" action="/admin/wheel/prize">
      <td style="{TD}"><input name="sort_order" type="number" value="{next_order}" style="{CELL_INPUT}width:50px;"></td>
      <td style="{TD}"><input name="label" placeholder="如 66666" style="{CELL_INPUT}width:110px;"></td>
      <td style="{TD}"><input name="min_coin" type="number" value="0" style="{CELL_INPUT}width:85px;"></td>
      <td style="{TD}"><input name="max_coin" type="number" value="0" style="{CELL_INPUT}width:85px;"></td>
      <td style="{TD}"><input name="weight" type="number" value="10" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}color:#9ca3af;">—</td>
      <td style="{TD}"><input name="daily_limit" type="number" value="0" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}"><input name="user_daily_limit" type="number" value="0" style="{CELL_INPUT}width:60px;"></td>
      <td style="{TD}color:#9ca3af;">—</td>
      <td style="{TD}">
        <select name="enabled" style="{CELL_INPUT}">
          <option value="true" selected>启用</option>
          <option value="false">停用</option>
        </select></td>
      <td style="{TD}"><button type="submit" style="{BTN}padding:5px 12px;background:#16a34a;">新增</button></td>
      </form>
    </tr>"""


@router.get("", response_class=HTMLResponse)
def show_wheel(
    msg: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    cfg = get_config(db)
    get_prizes(db)  # 第一次进来时写入默认的6个格子

    today = date.today()
    prizes = (
        db.query(WheelPrize)
        .order_by(WheelPrize.sort_order.asc(), WheelPrize.id.asc())
        .all()
    )
    taken = _taken_today(db, today)
    total_weight = sum(p.weight for p in prizes if p.is_enabled and p.weight > 0) or 1

    draw_count = (
        db.query(WheelDrawRecord).filter(WheelDrawRecord.stat_date == today).count()
    )
    coin_sum = sum(
        r.coin
        for r in db.query(WheelDrawRecord)
        .filter(
            WheelDrawRecord.stat_date == today,
            WheelDrawRecord.status == "claimed",
        )
        .all()
    )
    player_count = (
        db.query(WheelChance).filter(WheelChance.stat_date == today).count()
    )

    rows = "".join(
        _prize_row(
            p,
            (p.weight / total_weight * 100) if p.is_enabled and p.weight > 0 else 0,
            taken.get(p.id, 0),
        )
        for p in prizes
    )

    banner = ""
    if error:
        banner = (f'<div style="background:#fee2e2;color:#991b1b;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(error)}</div>')
    elif msg:
        banner = (f'<div style="background:#dcfce7;color:#166534;padding:10px 16px;'
                  f'border-radius:8px;margin-bottom:16px;">{html.escape(msg)}</div>')

    body = f"""
        <h1 style="color:#111827;">幸运转盘配置</h1>
        <p style="color:#6b7280;margin-bottom:16px;line-height:1.7;">
            用户每次抽奖前要完整看一个激励视频，看完服务端才扣次数、按权重定奖品、当场发金币。<br>
            抽奖次数和限量都按自然日算，零点自动重置。改完即时生效，不用重启服务。
        </p>
        {banner}

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">今日情况（{today}）</h2>
            <p style="color:#374151;font-size:15px;">
                参与 <b>{player_count}</b> 人，抽奖 <b>{draw_count}</b> 次，
                已发出 <b>{coin_sum:,}</b> 金币
            </p>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">基本设置</h2>
            <form method="post" action="/admin/wheel/save">
                <label style="{LABEL}">活动开关
                    <select name="enabled" style="{INPUT}">
                        <option value="true" {"selected" if cfg.is_enabled else ""}>开启</option>
                        <option value="false" {"" if cfg.is_enabled else "selected"}>关闭</option>
                    </select></label>
                <label style="{LABEL}">每日抽奖次数
                    <input name="daily_free_chances" type="number" value="{cfg.daily_free_chances}" required
                           style="{INPUT}width:90px;"></label>
                <label style="{LABEL}">两次抽奖最短间隔(秒)
                    <input name="min_interval_seconds" type="number" value="{cfg.min_interval_seconds}" required
                           style="{INPUT}width:90px;"></label>
                <br>
                <label style="{LABEL}">次数用完后看广告换次数
                    <select name="ad_chance_enabled" style="{INPUT}">
                        <option value="true" {"selected" if cfg.ad_chance_enabled else ""}>允许</option>
                        <option value="false" {"" if cfg.ad_chance_enabled else "selected"}>不允许</option>
                    </select></label>
                <label style="{LABEL}">每天最多换几次
                    <input name="ad_chance_max" type="number" value="{cfg.ad_chance_max}" required
                           style="{INPUT}width:90px;"></label>
                <div style="color:#9ca3af;font-size:13px;margin-bottom:14px;">
                    现在每抽一次本身就要看一个激励视频，"看广告换次数"再开等于一次抽奖看两个广告，一般选不允许、换次数填 0。
                </div>
                <label style="display:block;color:#374151;font-size:14px;margin-bottom:6px;">
                    抽奖规则文案（显示在转盘下方，留空用默认）</label>
                <textarea name="rules_text" rows="8"
                          style="{INPUT}width:100%;font-family:inherit;line-height:1.7;">{html.escape(cfg.rules_text or DEFAULT_RULES)}</textarea>
                <button type="submit" style="{BTN}margin-top:12px;">保存设置</button>
            </form>
        </div>

        <div style="{CARD}">
            <h2 style="margin-top:0;color:#111827;">奖品（转盘格子）</h2>
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;">
                <thead><tr>
                    <th style="{TH}">顺序</th><th style="{TH}">格子文案</th>
                    <th style="{TH}">金币下限</th><th style="{TH}">金币上限</th>
                    <th style="{TH}">权重</th><th style="{TH}">中奖率</th>
                    <th style="{TH}">每日限量</th><th style="{TH}">每人每日</th>
                    <th style="{TH}">今日已出</th><th style="{TH}">状态</th><th style="{TH}">操作</th>
                </tr></thead>
                <tbody>{rows}{_new_prize_row(len(prizes))}</tbody>
            </table>
            </div>
            <div style="color:#9ca3af;font-size:13px;line-height:1.9;margin-top:14px;">
                · 中奖率 = 本格权重 ÷ 所有启用格子权重之和，系统自己归一，加减格子不用重算。
                想让大奖 1%，给它权重 1、其他合计 99 即可。<br>
                · 金币下限和上限相同就是固定金额，不同就是区间内随机，格子文案写成 9999-18888 这种。<br>
                · 每日限量 = 全平台今天最多出几个，每人每日 = 同一个人今天最多中几次，0 都表示不限。
                抽完的格子会自动从候选里剔除，不会出现"中了发不出"。<br>
                · 转盘格子数 = 启用的格子个数，App 端按顺序动态画，改成 8 个也能正常显示，
                用户重进页面就生效。
            </div>
        </div>
    """
    return HTMLResponse(content=render_page("wheel", body, admin))


@router.post("/save")
def save_wheel(
    enabled: str = Form("true"),
    daily_free_chances: int = Form(...),
    ad_chance_enabled: str = Form("false"),
    ad_chance_max: int = Form(0),
    min_interval_seconds: int = Form(0),
    rules_text: str = Form(""),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    if daily_free_chances < 0 or ad_chance_max < 0 or min_interval_seconds < 0:
        return _redirect(error="次数和秒数不能是负数")

    cfg = get_config(db)
    cfg.is_enabled = enabled == "true"
    cfg.daily_free_chances = daily_free_chances
    cfg.ad_chance_enabled = ad_chance_enabled == "true"
    cfg.ad_chance_max = ad_chance_max
    cfg.min_interval_seconds = min_interval_seconds
    cfg.rules_text = rules_text.strip()
    db.commit()
    return _redirect(msg="转盘设置已保存")


@router.post("/prize")
def save_prize(
    prize_id: int = Form(0),
    label: str = Form(""),
    min_coin: int = Form(0),
    max_coin: int = Form(0),
    weight: int = Form(0),
    daily_limit: int = Form(0),
    user_daily_limit: int = Form(0),
    sort_order: int = Form(0),
    enabled: str = Form("true"),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    label = label.strip()
    if not label:
        return _redirect(error="格子文案不能为空")
    if min_coin < 0 or max_coin < 0:
        return _redirect(error="金币不能是负数")
    if max_coin < min_coin:
        return _redirect(error="金币上限不能小于下限")
    if weight < 0 or daily_limit < 0 or user_daily_limit < 0:
        return _redirect(error="权重和限量不能是负数")

    prize = (
        db.query(WheelPrize).filter(WheelPrize.id == prize_id).first()
        if prize_id
        else None
    )
    is_new = prize is None
    if is_new:
        prize = WheelPrize()
        db.add(prize)

    prize.label = label[:32]
    prize.min_coin = min_coin
    prize.max_coin = max_coin
    prize.weight = weight
    prize.daily_limit = daily_limit
    prize.user_daily_limit = user_daily_limit
    prize.sort_order = sort_order
    prize.is_enabled = enabled == "true"
    db.commit()
    return _redirect(msg=f"格子「{label}」已{'新增' if is_new else '保存'}")


@router.post("/prize/delete")
def delete_prize(
    prize_id: int = Form(...),
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin),
):
    prize = db.query(WheelPrize).filter(WheelPrize.id == prize_id).first()
    if prize is None:
        return _redirect(error="这个格子不存在，可能已经被删掉了")
    label = prize.label
    db.delete(prize)
    db.commit()
    return _redirect(msg=f"格子「{label}」已删除")
