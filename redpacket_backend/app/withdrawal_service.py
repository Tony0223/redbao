"""
提现业务：微信免确认收款授权 + 审核通过后自动打款（商家转账·用户授权免确认模式）。

WithdrawalRequest.status 约定：
- PENDING    用户已申请，金币已扣，等后台审核
- PROCESSING 已向微信发起转账，结果未最终确定（后台可"查单刷新"）
- SUCCESS    微信确认到账
- FAILED     失败或被驳回，金币已退回用户

资金安全规则：
- 每笔提现的商户单号 out_bill_no 生成后永不改变，重试/查单都用它
- 实际转账金额 transfer_fen 在第一次发起转账时确定，之后也不再改变
- 微信返回"结果不明确"时保持 PROCESSING，只查单，绝不退币、绝不换单号
- 只有查单确认微信那边没有这笔转账，才退还金币

补贴规则：审核（首次发起转账）时活动仍在进行，转账 = 提现金额 + 补贴；否则补贴清零，只打提现金额。

金币流水：扣币在 crud.create_withdrawal_request() 里记（WITHDRAW，负数），
退币统一在本文件的 _fail_and_refund() 里记（REFUND，正数）。
退币只有这一个入口，驳回和转账失败都走它，所以只在这一处记就是全的。
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import crud, models
from app.coin_models import CoinSource, log_coin
from app.wxpay import WxPayClient, WxPayError, get_client

logger = logging.getLogger("withdrawal")

AUTH_NONE = "NONE"
AUTH_WAITING = "WAIT_USER_CONFIRM"
AUTH_EFFECTIVE = "TAKING_EFFECT"
AUTH_PACKAGE_REUSE_HOURS = 23
MIN_TRANSFER_FEN = 10              # 微信单笔最低0.1元
REJECT_REMARK = "已驳回"
SUBSIDY_EXPIRED_REMARK = "活动已结束，补贴未发放"

S = models.WithdrawalStatus


class WithdrawalError(Exception):
    """业务错误，message 直接给用户或后台看。"""


def _now() -> datetime:
    return datetime.now()


def _client() -> WxPayClient:
    try:
        return get_client()
    except Exception as e:
        logger.error("微信支付未配置或配置有误: %s", e)
        raise WithdrawalError("提现通道暂未配置好，请联系客服")


def _auth_notify_url() -> str:
    base = os.getenv("WXPAY_NOTIFY_BASE", "").rstrip("/")
    return f"{base}/api/withdrawal/notify/authorization"


# ====================== 免确认收款授权 ======================

def is_authorized(user: models.User) -> bool:
    return bool(user.wx_auth_no) and user.wx_auth_state == AUTH_EFFECTIVE


def _save_auth_state(db: Session, user: models.User, state, authorization_id) -> None:
    if state:
        user.wx_auth_state = state
    if authorization_id:
        user.wx_auth_id = authorization_id
    if state and state != AUTH_WAITING:
        user.wx_auth_package = None
    db.add(user)
    db.commit()


def refresh_auth_state(db: Session, user: models.User, force: bool = False) -> str:
    if not user.wx_auth_no:
        return AUTH_NONE
    if user.wx_auth_state == AUTH_EFFECTIVE and not force:
        return AUTH_EFFECTIVE
    try:
        data = get_client().query_authorization(user.wx_auth_no)
    except Exception as e:
        logger.warning("查询授权状态失败 user=%s no=%s: %s", user.id, user.wx_auth_no, e)
        return user.wx_auth_state or AUTH_NONE
    _save_auth_state(db, user, data.get("state"), data.get("authorization_id"))
    return user.wx_auth_state or AUTH_NONE


def apply_authorization(db: Session, user: models.User) -> dict:
    if not user.openid:
        raise WithdrawalError("账号缺少微信身份信息，请退出后重新用微信登录")

    state = refresh_auth_state(db, user)
    if state == AUTH_EFFECTIVE:
        return {"authorized": True}

    client = _client()

    if (state == AUTH_WAITING and user.wx_auth_package and user.wx_auth_applied_at
            and _now() - user.wx_auth_applied_at < timedelta(hours=AUTH_PACKAGE_REUSE_HOURS)):
        return _launch_params(client, user.wx_auth_package)

    out_no = f"AU{user.id}T{int(time.time())}"
    try:
        data = client.apply_authorization(
            out_authorization_no=out_no,
            openid=user.openid,
            user_display_name=f"ID{user.id}",
            notify_url=_auth_notify_url(),
        )
    except WxPayError as e:
        logger.error("发起免确认收款授权失败 user=%s: %s", user.id, e)
        raise WithdrawalError(f"发起绑定失败：{e.message}")

    package_info = data.get("package_info")
    if not package_info:
        raise WithdrawalError("发起绑定失败：微信未返回授权信息")

    user.wx_auth_no = out_no
    user.wx_auth_state = AUTH_WAITING
    user.wx_auth_id = None
    user.wx_auth_package = package_info
    user.wx_auth_applied_at = _now()
    db.add(user)
    db.commit()
    return _launch_params(client, package_info)


def _launch_params(client: WxPayClient, package_info: str) -> dict:
    return {
        "authorized": False,
        "mch_id": client.mchid,
        "app_id": client.appid,
        "package": package_info,
    }


def handle_auth_notify(db: Session, headers, body: str) -> bool:
    try:
        client = get_client()
    except Exception as e:
        logger.error("收到授权回调但微信支付未配置: %s", e)
        return False

    if not client.verify_signature(headers, body):
        logger.warning("授权回调验签失败")
        return False
    try:
        data = client.decrypt_resource(json.loads(body)["resource"])
    except Exception as e:
        logger.error("授权回调解密失败: %s", e)
        return False

    logger.info("授权回调内容: %s", data)
    out_no = data.get("out_authorization_no")
    user = None
    if out_no:
        user = db.query(models.User).filter(models.User.wx_auth_no == out_no).first()
    if user is None:
        logger.warning("授权回调找不到对应用户 out_authorization_no=%s", out_no)
        return True

    _save_auth_state(db, user, data.get("state"), data.get("authorization_id"))
    return True


# ====================== 审核打款 ======================

def _single_limit_fen(db: Session) -> int:
    try:
        return int(round(float(crud.get_setting(db, "wxpay_single_limit_yuan", "50")) * 100))
    except ValueError:
        return 5000


def _decide_transfer_amount(db: Session, req: models.WithdrawalRequest) -> str:
    """
    第一次发起转账前确定实际转账金额，之后永不改变。
    返回需要写进备注的说明（补贴被取消时）。
    """
    if req.transfer_fen is not None:
        return SUBSIDY_EXPIRED_REMARK + "；" if (req.tier_id and not req.subsidy_fen) else ""

    note = ""
    if req.subsidy_fen:
        from app import subsidy_service  # 延迟导入，避免循环引用
        if not subsidy_service.is_active(db):
            req.subsidy_fen = 0
            note = SUBSIDY_EXPIRED_REMARK + "；"
    req.transfer_fen = req.yuan_amount + (req.subsidy_fen or 0)
    return note


def approve(db: Session, req: models.WithdrawalRequest) -> str:
    """后台点"审核通过"：向微信发起转账。返回给后台看的结果说明。"""
    if req.status != S.PENDING:
        raise WithdrawalError("只有待处理的申请才能审核通过")
    user = crud.get_user_by_id(db, req.user_id)
    if user is None:
        raise WithdrawalError("用户不存在")
    if not is_authorized(user):
        raise WithdrawalError("该用户还没绑定微信收款，无法自动打款")

    client = _client()

    note = _decide_transfer_amount(db, req)
    if req.transfer_fen < MIN_TRANSFER_FEN:
        raise WithdrawalError("金额低于微信单笔最低转账额 0.1 元")
    if req.transfer_fen > _single_limit_fen(db):
        raise WithdrawalError(f"转账金额 {req.transfer_fen / 100:.2f} 元超出单笔上限，请先在商户平台提额并修改后台配置")

    if not req.out_bill_no:
        req.out_bill_no = f"WD{req.id:010d}"   # 生成后永不改变
    req.status = S.PROCESSING
    req.remark = (note + "已发起转账")[:255]
    db.add(req)
    db.commit()

    try:
        data = client.transfer(req.out_bill_no, user.wx_auth_no, req.transfer_fen, remark="金石速答金币提现")
    except WxPayError as e:
        logger.error("转账请求失败 req=%s bill=%s: %s", req.id, req.out_bill_no, e)
        return note + _handle_transfer_error(db, client, req, user, e, note)
    return note + _apply_transfer_result(db, req, data, note)


def sync(db: Session, req: models.WithdrawalRequest) -> str:
    """后台点"查单刷新"：按原商户单号向微信查最新结果。"""
    if req.status != S.PROCESSING or not req.out_bill_no:
        raise WithdrawalError("只有打款中的申请才能查单")
    note = SUBSIDY_EXPIRED_REMARK + "；" if (req.tier_id and not req.subsidy_fen) else ""
    client = _client()
    try:
        data = client.query_transfer(req.out_bill_no)
    except WxPayError as e:
        if e.status_code == 404:
            req.status = S.PENDING
            req.remark = (note + "微信侧无此转账单，可重新审核")[:255]
            db.add(req)
            db.commit()
            return req.remark
        return f"查单失败，请稍后再试：{e.message}"
    return _apply_transfer_result(db, req, data, note)


def reject(db: Session, req: models.WithdrawalRequest) -> str:
    """后台点"驳回"：退还金币。发起过转账的单要先确认微信侧没有这笔转账。"""
    if req.status != S.PENDING:
        raise WithdrawalError("只有待处理的申请才能驳回")

    if req.out_bill_no:
        client = _client()
        try:
            data = client.query_transfer(req.out_bill_no)
        except WxPayError as e:
            if e.status_code != 404:
                raise WithdrawalError(f"无法确认微信侧状态，暂不能驳回：{e.message}")
        else:
            if data.get("state") not in ("FAIL", "CANCELLED"):
                raise WithdrawalError("该单在微信侧已创建转账，不能驳回，请先查单")

    _fail_and_refund(db, req, REJECT_REMARK)
    return "已驳回，金币已退回用户"


def _handle_transfer_error(db, client, req, user, e: WxPayError, note: str) -> str:
    if e.is_uncertain:
        req.remark = (note + f"结果不明确({e.code})，请稍后点查单")[:255]
        db.add(req)
        db.commit()
        return f"结果不明确({e.code})，请稍后点查单"

    if e.code == "NOT_ENOUGH":
        req.status = S.PENDING
        req.remark = (note + "运营账户余额不足，请充值后重新审核")[:255]
        db.add(req)
        db.commit()
        return "运营账户余额不足，请充值后重新审核"

    try:
        data = client.query_transfer(req.out_bill_no)
    except WxPayError as qe:
        if qe.status_code == 404:
            _fail_and_refund(db, req, note + f"{e.code}: {e.message}")
            refresh_auth_state(db, user, force=True)
            return f"打款失败，金币已退回：{e.message}"
        req.remark = (note + f"发起失败({e.code})且查单失败，请稍后点查单")[:255]
        db.add(req)
        db.commit()
        return f"发起失败({e.code})且查单失败，请稍后点查单"
    return _apply_transfer_result(db, req, data, note)


def _apply_transfer_result(db: Session, req: models.WithdrawalRequest, data: dict, note: str = "") -> str:
    state = data.get("state", "")
    if data.get("transfer_bill_no"):
        req.wechat_transfer_no = data["transfer_bill_no"]

    if state == "SUCCESS":
        req.status = S.SUCCESS
        req.remark = (note + "已到账")[:255]
        req.processed_at = _now()
        db.add(req)
        db.commit()
        return "打款成功，已到账"

    if state in ("FAIL", "CANCELLED"):
        reason = data.get("fail_reason") or state
        _fail_and_refund(db, req, note + f"微信转账失败：{reason}")
        return f"打款失败，金币已退回：{reason}"

    req.status = S.PROCESSING
    req.remark = (note + f"微信处理中({state})，请稍后点查单")[:255]
    db.add(req)
    db.commit()
    return f"微信处理中({state})，请稍后点查单"


def _fail_and_refund(db: Session, req: models.WithdrawalRequest, remark: str) -> None:
    if req.status in (S.SUCCESS, S.FAILED):
        return   # 防止重复退币
    user = crud.get_user_by_id(db, req.user_id)
    if user is not None:
        user.coin_balance += req.coin_amount
        db.add(user)
        # 退币只有这一个入口（驳回、转账失败、发起失败后查无此单都走这里），
        # 所以流水只在这记一次，不会重复也不会漏
        log_coin(
            db, user.id, CoinSource.REFUND, req.coin_amount,
            remark=f"提现#{req.id}退回", balance_after=user.coin_balance,
        )
    req.status = S.FAILED
    req.remark = remark[:255]
    req.processed_at = _now()
    db.add(req)
    db.commit()
