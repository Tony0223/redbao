"""
从穿山甲 GroMore「聚合数据API」拉每天的真实收益(收益API / api_revenue)，存进 real_revenue_daily。

接口：GET https://www.csjplatform.com/union_media/open/api/mediation/get_daily_income_report_data
鉴权：参数(去掉 sign 和空值)按字典序拼成 k1=v1&k2=v2...，末尾直接接 security_key，再 MD5(32位小写)。
     天级报表用 timestamp(秒)，3 分钟内有效。

注意(来自官方文档)：
- 「今天」的数据要单独查，api 相关字段不支持当天查询 → 只拉昨天及以前。
- 前一天的数据一般次日 14:00 之后才处理完 → 次日 14:00 之前不入库，避免存进不完整的数。
- 三方广告网络的 API 数据可能事后修正 → 定时任务每天重拉最近 7 天覆盖。
- 子账号要有“查看全部数据”权限，否则拿不到 revenue 类字段(错误码 118)。

配置(后台“代理商管理 → 穿山甲真实收益”页面里填，存在 app_settings 表)：
  gromore_user_id / gromore_role_id / gromore_security_key / gromore_site_ids(选填)
"""
import hashlib
import logging
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
from sqlalchemy.orm import Session

from app import crud
from app.agent_models import RealRevenueDaily

logger = logging.getLogger("gromore")

API_URL = "https://www.csjplatform.com/union_media/open/api/mediation/get_daily_income_report_data"
READY_HOUR = 14          # 次日几点之后认为前一天数据已出
PAGE_LIMIT = 5000
MAX_SYNC_DAYS = 31

KEY_USER_ID = "gromore_user_id"
KEY_ROLE_ID = "gromore_role_id"
KEY_SECURITY = "gromore_security_key"
KEY_SITE_IDS = "gromore_site_ids"
KEY_LAST_SYNC = "gromore_last_sync"

ERROR_CODES = {
    "101": "身份验证失败(检查 security key / user_id / role_id)",
    "102": "无效的 user_id",
    "107": "子账号无访问权限",
    "108": "穿山甲服务异常，稍后重试",
    "114": "日期跨度不符合规则",
    "115": "参数错误",
    "116": "穿山甲服务内部错误，稍后重试",
    "117": "子账号没有应用权限",
    "118": "子账号没有 ecpm/revenue 查看权限(主账号在“角色管理”里给该角色配置“查看全部数据”)",
    "119": "子账号必须填写应用ID(site_id)",
}


class GroMoreError(Exception):
    pass


# ==================== 配置 ====================

def get_config(db: Session) -> dict:
    return {
        "user_id": crud.get_setting(db, KEY_USER_ID, "").strip(),
        "role_id": crud.get_setting(db, KEY_ROLE_ID, "").strip(),
        "security_key": crud.get_setting(db, KEY_SECURITY, "").strip(),
        "site_ids": crud.get_setting(db, KEY_SITE_IDS, "").strip(),
    }


def is_configured(cfg: dict) -> bool:
    return bool(cfg["user_id"] and cfg["role_id"] and cfg["security_key"])


def save_config(db: Session, user_id: str, role_id: str, security_key: str, site_ids: str) -> None:
    """security_key 留空表示不修改(页面上不回显密钥)。"""
    for raw, name in ((user_id, "user_id"), (role_id, "role_id")):
        if raw and not raw.isdigit():
            raise GroMoreError(f"{name} 只能是数字")
    site_ids = ",".join(s.strip() for s in site_ids.replace("，", ",").split(",") if s.strip())
    if site_ids and not all(s.isdigit() for s in site_ids.split(",")):
        raise GroMoreError("应用ID只能是数字，多个用逗号分隔")
    crud.set_setting(db, KEY_USER_ID, user_id, "穿山甲 GroMore 数据API：媒体账号 user_id")
    crud.set_setting(db, KEY_ROLE_ID, role_id, "穿山甲 GroMore 数据API：role_id")
    crud.set_setting(db, KEY_SITE_IDS, site_ids, "穿山甲 GroMore 数据API：只统计这些应用ID(选填)")
    if security_key:
        crud.set_setting(db, KEY_SECURITY, security_key, "穿山甲 GroMore 数据API：security key")
    db.commit()


# ==================== 接口调用 ====================

def sign_params(params: dict, security_key: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sign" and v is not None and str(v) != "")
    raw = "&".join(f"{k}={v}" for k, v in items)
    return hashlib.md5((raw + security_key).encode("utf-8")).hexdigest()


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v).strip() or "0")
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _to_int(v) -> int:
    try:
        return int(Decimal(str(v).strip() or "0"))
    except (InvalidOperation, ValueError):
        return 0


def fetch_day(cfg: dict, d: date) -> dict:
    """
    查某一天整个账号(或指定应用)的汇总。返回
    {"revenue_yuan": Decimal|None, "api_imp_cnt": int, "imp_cnt": int, "currency": str}
    revenue_yuan 为 None 表示接口没返回 api_revenue 字段。
    """
    total_rev = Decimal(0)
    has_api_rev = False
    api_imp = imp = 0
    currency = ""
    offset = 0
    while True:
        params = {
            "user_id": cfg["user_id"],
            "role_id": cfg["role_id"],
            "version": "2.0",
            "sign_type": "MD5",
            "timestamp": int(time.time()),
            "start_date": d.isoformat(),
            "end_date": d.isoformat(),
            "dimensions": "site_id",
            "metrics": "api_revenue,api_imp_cnt,imp_cnt,revenue",
            "limit": PAGE_LIMIT,
            "offset": offset,
        }
        if cfg.get("site_ids"):
            params["site_ids"] = cfg["site_ids"]
        params["sign"] = sign_params(params, cfg["security_key"])
        try:
            resp = requests.get(API_URL, params=params, timeout=30)
            body = resp.json()
        except requests.RequestException as e:
            raise GroMoreError(f"请求穿山甲失败：{e}")
        except ValueError:
            raise GroMoreError(f"穿山甲返回的不是 JSON(HTTP {resp.status_code})")

        code = str(body.get("code", ""))
        if code != "100":
            reason = ERROR_CODES.get(code, "")
            raise GroMoreError(f"穿山甲返回错误 {code} {reason} {body.get('message') or ''}".strip())

        data = body.get("data") or {}
        currency = currency or str(data.get("currency") or "")
        items = data.get("report_list") or []
        for it in items:
            if "api_revenue" in it:
                has_api_rev = True
                total_rev += _to_decimal(it.get("api_revenue"))
            api_imp += _to_int(it.get("api_imp_cnt"))
            imp += _to_int(it.get("imp_cnt"))
        if str(data.get("has_next", body.get("has_next", 0))) != "1" or not items:
            break
        offset += len(items)

    return {
        "revenue_yuan": total_rev if has_api_rev else None,
        "api_imp_cnt": api_imp,
        "imp_cnt": imp,
        "currency": currency or "cny",
    }


def data_ready(d: date, now: datetime = None) -> bool:
    now = now or datetime.now()
    return now >= datetime(d.year, d.month, d.day) + timedelta(days=1, hours=READY_HOUR)


def sync_day(db: Session, cfg: dict, d: date) -> str:
    """拉一天并入库，返回结果说明。不满足条件的不入库(保留原来的数)。"""
    if not data_ready(d):
        return f"{d} 数据未出(次日{READY_HOUR}点后才完整)，跳过"
    r = fetch_day(cfg, d)
    if r["currency"].lower() != "cny":
        return f"{d} 账号币种是 {r['currency']}，暂不支持，未入库"
    if r["revenue_yuan"] is None:
        if r["imp_cnt"] > 0:
            return f"{d} 穿山甲没有返回收益API(检查 GroMore 广告网络是否授权 Reporting API)，未入库"
        r["revenue_yuan"] = Decimal(0)   # 当天没有任何展示，真实收益就是 0
    if r["api_imp_cnt"] == 0 and r["imp_cnt"] > 0:
        return f"{d} 收益API数据还没回传(展示API=0)，未入库"

    row = db.query(RealRevenueDaily).filter(RealRevenueDaily.report_date == d).first()
    if row is None:
        row = RealRevenueDaily(report_date=d)
        db.add(row)
    row.revenue_fen = (r["revenue_yuan"] * 100).quantize(Decimal("0.0001"))
    row.api_imp_cnt = r["api_imp_cnt"]
    row.imp_cnt = r["imp_cnt"]
    row.currency = r["currency"].lower()
    row.fetched_at = datetime.now()
    db.commit()
    return f"{d} 收益API ¥{r['revenue_yuan']:.2f}"


def sync_range(db: Session, start: date, end: date) -> list:
    """拉 [start, end] 每一天。返回每天的结果说明。"""
    cfg = get_config(db)
    if not is_configured(cfg):
        raise GroMoreError("还没有配置穿山甲 user_id / role_id / security key")
    yesterday = date.today() - timedelta(days=1)
    end = min(end, yesterday)
    if end < start:
        raise GroMoreError("只能拉取昨天及以前的数据")
    if (end - start).days + 1 > MAX_SYNC_DAYS:
        raise GroMoreError(f"一次最多拉 {MAX_SYNC_DAYS} 天")
    results = []
    d = start
    while d <= end:
        try:
            results.append(sync_day(db, cfg, d))
        except GroMoreError as e:
            db.rollback()
            results.append(f"{d} 失败：{e}")
        d += timedelta(days=1)
    summary = f"{datetime.now():%Y-%m-%d %H:%M} 拉取 {start}~{end}：" + "；".join(results)
    crud.set_setting(db, KEY_LAST_SYNC, summary[:1000], "穿山甲 GroMore 最近一次拉取结果")
    db.commit()
    return results


def sync_recent(db: Session, days: int = 7) -> list:
    yesterday = date.today() - timedelta(days=1)
    return sync_range(db, yesterday - timedelta(days=days - 1), yesterday)


def list_real(db: Session, start: date, end: date) -> dict:
    rows = (db.query(RealRevenueDaily)
            .filter(RealRevenueDaily.report_date >= start, RealRevenueDaily.report_date <= end)
            .all())
    return {r.report_date: r for r in rows}
