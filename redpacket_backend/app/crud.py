"""
核心业务逻辑层。

金币计算规则严格按照管理后台"低区/高区收益配置"页的字段含义实现：
- 看一次广告，随机发 [min_coin, max_coin] 之间的金币
  - 插屏广告(interstitial)：上限用 interstitial_max_coin
  - 其他广告类型：is_game_ad=True 用 max_coin_game，否则用 max_coin_default
- 每看满 bonus_threshold_count 个广告，额外赐福 bonus_amount 个金币
  （bonus_threshold_count 或 bonus_amount 任一为0，则赐福规则不生效）

团长返利规则：
- 如果这个用户是被别人邀请注册的(invited_by_user_id有值)，
  他每次看广告拿到金币后，邀请他的那个人(团长)按 RebateConfig 配置的模式抽成
  - 百分比模式：团员本次拿到金币 * percentage_value / 100
  - 固定模式：不管团员拿多少，团长固定拿 fixed_value
  每笔返利写一条 RebateLog，用于邀请页统计和收益明细

金币流水：
- 所有发币的地方都往 coin_logs 写一条（log_coin），"我的 → 收入明细"只查这一张表。
  各玩法自己的表（AdWatchLog / RebateLog / SignInLog / PunchLog…）照旧，
  它们管各自的业务逻辑，coin_logs 只管记账。
"""
import random
import secrets
import string

from sqlalchemy.orm import Session

from app import models, schemas
from app.coin_models import CoinSource, log_coin


def get_or_create_reward_config(db: Session, tier: models.UserTier) -> models.RewardConfig:
    config = (
        db.query(models.RewardConfig)
        .filter(models.RewardConfig.tier == tier)
        .first()
    )
    if config is None:
        config = models.RewardConfig(tier=tier)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_or_create_rebate_config(db: Session) -> models.RebateConfig:
    """团长返利配置是全局单例，只有一条记录。"""
    config = db.query(models.RebateConfig).first()
    if config is None:
        config = models.RebateConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def credit_rebate_if_applicable(
    db: Session, invitee: models.User, invitee_total_this_time: int, ad_log_id: int | None = None
) -> None:
    """团员看完广告拿到金币后调这个，检查有没有团长、有的话按规则给团长加钱并记流水。"""
    if invitee.invited_by_user_id is None:
        return
    leader = get_user_by_id(db, invitee.invited_by_user_id)
    if leader is None:
        return

    config = get_or_create_rebate_config(db)
    if config.mode == models.RebateMode.PERCENTAGE:
        rebate = int(invitee_total_this_time * config.percentage_value / 100)
    else:
        rebate = config.fixed_value

    if rebate <= 0:
        return

    leader.coin_balance += rebate
    leader.total_rebate_coins = (leader.total_rebate_coins or 0) + rebate
    db.add(leader)
    db.add(models.RebateLog(
        leader_user_id=leader.id,
        invitee_user_id=invitee.id,
        ad_log_id=ad_log_id,
        coin_amount=rebate,
    ))
    log_coin(
        db, leader.id, CoinSource.REBATE, rebate,
        remark=f"徒弟{invitee.id}看广告", balance_after=leader.coin_balance,
    )
    db.commit()


def calculate_ad_reward(
    db: Session, user: models.User, ad_type: models.AdType, is_game_ad: bool
) -> schemas.AdRewardResponse:
    config = get_or_create_reward_config(db, user.tier)

    if ad_type == models.AdType.INTERSTITIAL:
        max_coin = config.interstitial_max_coin
    else:
        max_coin = config.max_coin_game if is_game_ad else config.max_coin_default

    min_coin = min(config.min_coin, max_coin)
    reward_amount = random.randint(min_coin, max_coin)

    user.ad_watch_count += 1
    bonus_amount = 0
    if config.bonus_threshold_count > 0 and config.bonus_amount > 0:
        if user.ad_watch_count % config.bonus_threshold_count == 0:
            bonus_amount = config.bonus_amount

    total_this_time = reward_amount + bonus_amount
    user.coin_balance += total_this_time
    user.total_ad_coins = (user.total_ad_coins or 0) + total_this_time

    log = models.AdWatchLog(
        user_id=user.id,
        ad_type=ad_type,
        is_game_ad=is_game_ad,
        reward_amount=reward_amount,
        bonus_amount=bonus_amount,
    )
    db.add(log)
    db.add(user)
    log_coin(
        db, user.id, CoinSource.AD, total_this_time,
        remark=f"赐福+{bonus_amount}" if bonus_amount else "",
        balance_after=user.coin_balance,
    )
    db.commit()
    db.refresh(user)

    # 看完广告、金币到账之后，顺手结算团长抽成（记下来源广告记录，方便对账）
    credit_rebate_if_applicable(db, user, total_this_time, ad_log_id=log.id)

    return schemas.AdRewardResponse(
        reward_amount=reward_amount,
        bonus_amount=bonus_amount,
        total_this_time=total_this_time,
        new_balance=user.coin_balance,
        ad_watch_count=user.ad_watch_count,
    )


def get_user_by_id(db: Session, user_id: int) -> models.User | None:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_token(db: Session, token: str) -> models.User | None:
    return db.query(models.User).filter(models.User.token == token).first()


def issue_login_token(db: Session, user: models.User) -> str:
    """
    登录成功时调用，生成一个新的随机token、覆盖旧的（旧token自动失效），
    返回这个新token给路由层，路由层再传给App。
    """
    new_token = secrets.token_hex(32)
    user.token = new_token
    db.add(user)
    db.commit()
    db.refresh(user)
    return new_token


def clear_token(db: Session, user: models.User) -> None:
    """退出登录：把token清空，App下次拿这个旧token请求会被401拒绝，逼它重新走登录流程。"""
    user.token = None
    db.add(user)
    db.commit()


def get_user_by_openid(db: Session, openid: str) -> models.User | None:
    return db.query(models.User).filter(models.User.openid == openid).first()


def get_user_by_invite_code(db: Session, invite_code: str) -> models.User | None:
    return db.query(models.User).filter(models.User.invite_code == invite_code).first()


def generate_unique_invite_code(db: Session) -> str:
    """6位大写字母+数字的邀请码，生成后检查数据库里没重复的才返回。"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=6))
        if get_user_by_invite_code(db, code) is None:
            return code


def create_user(
    db: Session,
    openid: str | None,
    nickname: str | None,
    inviter_code: str | None = None,
    avatar_url: str | None = None,
) -> models.User:
    """
    inviter_code：新用户注册时如果是通过别人的邀请链接/邀请码进来的，
    传这个人的invite_code，会自动绑定"这个新用户属于哪个团长"。

    avatar_url：微信头像地址，登录时从 sns/userinfo 取到的，可能为空。
    """
    user = models.User(openid=openid, nickname=nickname, avatar_url=avatar_url or None)
    user.invite_code = generate_unique_invite_code(db)

    if inviter_code:
        inviter = get_user_by_invite_code(db, inviter_code)
        if inviter is not None:
            user.invited_by_user_id = inviter.id

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_setting(db: Session, key: str, default: str = "") -> str:
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    return setting.value if setting and setting.value is not None else default


def set_setting(db: Session, key: str, value: str, description: str = "") -> models.AppSetting:
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    if setting is None:
        setting = models.AppSetting(key=key, value=value, description=description)
        db.add(setting)
    else:
        setting.value = value
        if description:
            setting.description = description
    db.commit()
    db.refresh(setting)
    return setting


# 预置的设置项：key -> (默认值, 中文说明)。后台/admin/settings页面就是按这个列表渲染的。
DEFAULT_SETTINGS = {
    "latest_version_name": ("1.0.0", "最新版本号（显示给用户看的，比如1.2.0）"),
    "latest_version_code": ("1", "最新版本号（整数，App内部判断是否需要更新用）"),
    "update_notes": ("", "更新说明文案"),
    "update_url": ("", "新版本下载链接"),
    "force_update": ("false", "是否强制更新，true或false"),
    "contact_wechat": ("", "客服微信号"),
    "contact_qq": ("", "客服QQ号"),
    "contact_phone": ("", "客服电话"),
    "exchange_rate_coins_per_yuan": ("100000", "多少金币兑换1元人民币"),
    "min_withdraw_coins": ("500000", "最低多少金币才能申请提现"),
    "app_download_url": ("https://fir.xcxwo.com/sd9efqvp", "邀请落地页“立即下载”的地址(fir.im分发)"),
    "site_enabled": ("true", "网站总开关，true=用户可访问，false=只显示关闭提示"),
    "site_closed_msg": ("网站已关闭，请联系管理员", "网站关闭时给用户看的提示"),
    "subsidy_enabled": ("false", "提现补贴活动开关，true或false"),
    "subsidy_end_at": ("", "提现补贴活动结束时间"),
    "wxpay_single_limit_yuan": ("50", "微信商家转账单笔上限（元），要和商户平台设置一致"),
    "punch_enabled": ("true", "每日打卡开关，true或false"),
    "punch_start_time": ("07:00:00", "打卡开始时间"),
    "punch_end_time": ("11:00:00", "打卡结束时间"),
    "punch_publish_time": ("11:10:00", "开奖公布时间"),
    "punch_base_pool": ("0", "每日固定底池金币数"),
    "punch_inject_min": ("0", "打卡注入奖池的金币下限（0表示不注入）"),
    "punch_inject_max": ("0", "打卡注入奖池的金币上限"),
    "punch_rules": ("", "打卡规则文案，App规则弹窗显示"),
    # 下面三项在 /admin/content 那个页面里编辑，内容长，不在 /admin/settings 显示
    "notice_content": ("", "平台公告内容，App我的页显示"),
    "privacy_content": ("", "隐私政策内容，上架审核必填"),
    "agreement_content": ("", "用户协议内容"),
}


def ensure_default_settings(db: Session) -> None:
    """启动时调一次，把预置的设置项缺的都补上默认值，已存在的不动。"""
    for key, (default_value, description) in DEFAULT_SETTINGS.items():
        existing = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
        if existing is None:
            db.add(models.AppSetting(key=key, value=default_value, description=description))
    db.commit()


def create_withdrawal_request(db: Session, user: models.User, coin_amount: int) -> models.WithdrawalRequest:
    exchange_rate = int(get_setting(db, "exchange_rate_coins_per_yuan", "100000"))
    yuan_amount_fen = int(coin_amount / exchange_rate * 100)  # 存分，避免小数精度问题

    user.coin_balance -= coin_amount
    db.add(user)

    request = models.WithdrawalRequest(
        user_id=user.id,
        coin_amount=coin_amount,
        yuan_amount=yuan_amount_fen,
        status=models.WithdrawalStatus.PENDING,
    )
    db.add(request)
    log_coin(
        db, user.id, CoinSource.WITHDRAW, -coin_amount,
        remark="申请提现", balance_after=user.coin_balance,
    )
    db.commit()
    db.refresh(request)
    return request


def list_withdrawals_by_user(db: Session, user_id: int):
    """查某用户的提现申请记录，最新的在前。"""
    return (
        db.query(models.WithdrawalRequest)
        .filter(models.WithdrawalRequest.user_id == user_id)
        .order_by(models.WithdrawalRequest.created_at.desc())
        .all()
    )


# ==================== 后台管理账号 / 权限 ====================
import hashlib as _hashlib


def hash_password(password: str, salt: str = None) -> str:
    """pbkdf2 存成 "salt$hash"，不存明文。"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = _hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt = stored.split("$", 1)[0]
    return secrets.compare_digest(hash_password(password, salt), stored)


def get_admin_user(db: Session, username: str):
    return db.query(models.AdminUser).filter(models.AdminUser.username == username).first()


def get_admin_user_by_id(db: Session, uid: int):
    return db.query(models.AdminUser).filter(models.AdminUser.id == uid).first()


def list_admin_users(db: Session):
    return db.query(models.AdminUser).order_by(models.AdminUser.id.asc()).all()


def create_admin_user(db: Session, username: str, password: str,
                      is_super: bool, allowed_menus: str):
    user = models.AdminUser(
        username=username,
        password_hash=hash_password(password),
        is_super=is_super,
        allowed_menus=allowed_menus or "",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_admin_user(db: Session, uid: int, allowed_menus: str = None,
                      password: str = None):
    user = get_admin_user_by_id(db, uid)
    if user is None:
        return None
    if allowed_menus is not None:
        user.allowed_menus = allowed_menus
    if password:
        user.password_hash = hash_password(password)
    db.commit()
    return user


def delete_admin_user(db: Session, uid: int):
    user = get_admin_user_by_id(db, uid)
    if user is None or user.is_super:
        return False   # 超管不允许删
    db.delete(user)
    db.commit()
    return True


def ensure_super_admin(db: Session, username: str, password: str) -> None:
    """启动时确保存在一个超管账号；没有任何超管则用env里的账号密码建一个。"""
    exists = db.query(models.AdminUser).filter(models.AdminUser.is_super == True).first()  # noqa: E712
    if exists:
        return
    # 若同名普通账号已存在则升级为超管，否则新建
    same = get_admin_user(db, username)
    if same:
        same.is_super = True
        db.commit()
        return
    create_admin_user(db, username, password, is_super=True, allowed_menus="")
