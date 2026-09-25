"""
数据库模型定义。

核心表：
- User：用户，记录微信openid和金币余额
- AdWatchLog：每次看广告的流水记录
- RebateLog：团长返利流水
- SignInConfig / SignInLog：每日签到配置和流水
- SubsidyTier：提现补贴档位
- RewardConfig：金币奖励规则配置（对应管理后台"低区/高区收益配置"那几个Tab页的数值）
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserTier(str, enum.Enum):
    """用户分档：对应后台"低区收益配置"/"高区收益配置"两个Tab。"""
    LOW = "low"
    HIGH = "high"


class AdType(str, enum.Enum):
    """广告类型：跟后台配置页里出现的广告类型对应。"""
    REWARD_VIDEO = "reward_video"      # 激励视频（红包群点红包用的这种）
    FEED = "feed"                       # 信息流
    INTERSTITIAL = "interstitial"       # 插屏
    BANNER = "banner"                   # banner


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    openid = Column(String(64), unique=True, index=True, nullable=True)

    nickname = Column(String(64), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    coin_balance = Column(Integer, nullable=False, default=0)
    tier = Column(Enum(UserTier), nullable=False, default=UserTier.LOW)

    # 累计看广告次数，用于判断"看满N个广告赐福"的赐福逻辑
    ad_watch_count = Column(Integer, nullable=False, default=0)

    # 邀请体系：每个用户有自己的邀请码，别人用这个码注册就跟自己绑定"团长-团员"关系
    invite_code = Column(String(16), unique=True, index=True, nullable=True)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 登录令牌
    token = Column(String(64), unique=True, index=True, nullable=True)

    # 累计收益统计（只做统计，可用余额仍然只看 coin_balance）
    total_ad_coins = Column(Integer, nullable=False, default=0)      # 累计看广告所得
    total_rebate_coins = Column(Integer, nullable=False, default=0)  # 累计推广返利所得

    # 签到：连续签了几天、最后签到日期。断签后 streak 从1重新开始
    signin_streak = Column(Integer, nullable=False, default=0)
    last_signin_date = Column(Date, nullable=True)

    # 微信"免确认收款授权"（商家转账提现用）
    wx_auth_no = Column(String(32), unique=True, index=True, nullable=True)  # 商户侧授权单号
    wx_auth_state = Column(String(32), nullable=True)      # WAIT_USER_CONFIRM / TAKING_EFFECT / CLOSED
    wx_auth_id = Column(String(64), nullable=True)         # 微信侧授权单号
    wx_auth_package = Column(Text, nullable=True)          # 待确认时拉起授权页用的package，24小时内可复用
    wx_auth_applied_at = Column(DateTime, nullable=True)   # 发起授权的时间

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ad_logs = relationship("AdWatchLog", back_populates="user")


class AdWatchLog(Base):
    __tablename__ = "ad_watch_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    ad_type = Column(Enum(AdType), nullable=False)
    is_game_ad = Column(Boolean, nullable=False, default=False)

    reward_amount = Column(Integer, nullable=False)            # 这次基础奖励的金币数
    bonus_amount = Column(Integer, nullable=False, default=0)  # 赐福部分

    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="ad_logs")


class RebateLog(Base):
    """团长返利流水：团员每看一次广告触发的团长抽成，一次一条。"""
    __tablename__ = "rebate_logs"

    id = Column(Integer, primary_key=True, index=True)
    leader_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    invitee_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ad_log_id = Column(Integer, ForeignKey("ad_watch_logs.id"), nullable=True)
    coin_amount = Column(Integer, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), index=True)


class SignInConfig(Base):
    """
    签到周期配置：一行一天。第1天签多少、第2天签多少……
    后台可以增删行来改变周期长度（默认7天一轮）。
    """
    __tablename__ = "signin_configs"

    id = Column(Integer, primary_key=True, index=True)
    day_index = Column(Integer, nullable=False, unique=True)  # 第几天，从1开始
    coins = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SignInLog(Base):
    """
    签到流水。(user_id, signin_date) 唯一，靠数据库约束挡住同一天重复签到。
    """
    __tablename__ = "signin_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    signin_date = Column(Date, nullable=False)
    day_index = Column(Integer, nullable=False)   # 这次签的是周期里的第几天
    coins = Column(Integer, nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "signin_date", name="uq_signin_user_date"),)


class PunchLog(Base):
    """
    每日打卡记录。rank_no 是当天的打卡名次（越早越小）。
    (user_id, punch_date) 唯一，挡住同一天重复打卡。
    """
    __tablename__ = "punch_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    punch_date = Column(Date, nullable=False)
    rank_no = Column(Integer, nullable=False)          # 当天第几个打卡
    weight = Column(Integer, nullable=False, default=0)  # 打卡时的活跃权重（累计看广告次数）
    injected_coins = Column(Integer, nullable=False, default=0)  # 这次打卡往奖池注入了多少
    reward_coins = Column(Integer, nullable=False, default=0)    # 最终分到多少
    rewarded = Column(Boolean, nullable=False, default=False)    # 奖励是否已发放

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "punch_date", name="uq_punch_user_date"),)


class PunchPool(Base):
    """每日打卡奖金池，一天一条。"""
    __tablename__ = "punch_pools"

    id = Column(Integer, primary_key=True, index=True)
    punch_date = Column(Date, nullable=False, unique=True)
    base_coins = Column(Integer, nullable=False, default=0)       # 后台配的固定底池
    injected_coins = Column(Integer, nullable=False, default=0)   # 用户打卡看广告注入的部分
    punch_count = Column(Integer, nullable=False, default=0)
    published = Column(Boolean, nullable=False, default=False)    # 是否已开奖
    published_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

class SubsidyTier(Base):
    """
    提现补贴档位：用户选某一档提现，审核通过时活动仍在进行，实际到账 = 提现金额 × (1 + 补贴比例)。
    档位不删除，不用了改成停用（历史提现记录会引用档位ID）。
    """
    __tablename__ = "subsidy_tiers"

    id = Column(Integer, primary_key=True, index=True)
    withdraw_fen = Column(Integer, nullable=False)                   # 提现金额（分）
    percent = Column(Integer, nullable=False, default=0)             # 补贴比例，40 表示 40%
    per_user_limit = Column(Integer, nullable=False, default=1)      # 每人限几次，0 表示不限
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)          # 越小越靠前

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RewardConfig(Base):
    """奖励规则配置表——对应管理后台"低区收益配置"页的数值。"""
    __tablename__ = "reward_configs"

    id = Column(Integer, primary_key=True, index=True)
    tier = Column(Enum(UserTier), nullable=False, unique=True)

    min_coin = Column(Integer, nullable=False, default=50)
    max_coin_default = Column(Integer, nullable=False, default=50000)
    max_coin_game = Column(Integer, nullable=False, default=20000)
    interstitial_max_coin = Column(Integer, nullable=False, default=2000)

    bonus_threshold_count = Column(Integer, nullable=False, default=10)
    bonus_amount = Column(Integer, nullable=False, default=2)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RebateMode(str, enum.Enum):
    """团长抽成模式：后台二选一，切换后立刻按新模式算。"""
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "pending"        # 用户刚提交，金币已扣，等后台审核
    PROCESSING = "processing"  # 已向微信发起转账，结果还没最终确定
    SUCCESS = "success"        # 打款成功
    FAILED = "failed"          # 打款失败或被驳回，金币已退回


class RebateConfig(Base):
    """团长返利规则配置——单例表，全局只有一条配置。"""
    __tablename__ = "rebate_configs"

    id = Column(Integer, primary_key=True, index=True)
    mode = Column(Enum(RebateMode), nullable=False, default=RebateMode.PERCENTAGE)
    percentage_value = Column(Integer, nullable=False, default=10)
    fixed_value = Column(Integer, nullable=False, default=100)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WithdrawalRequest(Base):
    """
    提现申请记录。后台"审核通过"后自动调微信商家转账（用户授权免确认模式）打款。
    """
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    coin_amount = Column(Integer, nullable=False)   # 扣除的金币数
    yuan_amount = Column(Integer, nullable=False)   # 提现金额（分），不含补贴

    # 平台补贴：补贴档位提现才有
    tier_id = Column(Integer, nullable=True)                   # 补贴档位ID，普通提现为空
    subsidy_fen = Column(Integer, nullable=False, default=0)   # 补贴（分）：申请时锁定；审核时活动已结束则清零
    transfer_fen = Column(Integer, nullable=True)              # 实际转账金额（分），首次发起转账时确定，之后不变

    status = Column(Enum(WithdrawalStatus), nullable=False, default=WithdrawalStatus.PENDING)

    # 商户单号：第一次发起转账时生成，之后永不改变
    out_bill_no = Column(String(32), unique=True, nullable=True)
    wechat_transfer_no = Column(String(64), nullable=True)
    remark = Column(String(255), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)


class AppSetting(Base):
    """通用键值配置表。"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    value = Column(String(500), nullable=True)
    description = Column(String(255), nullable=True)

class AdminUser(Base):
    """后台管理账号。

    - is_super=True 为最高权限(admin)，能看所有菜单、能管理其他后台账号；
    - 普通账号只能看 allowed_menus 里列出的菜单(逗号分隔的菜单key)。
    密码用 pbkdf2 存成 "salt$hash"，不存明文。
    """
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_super = Column(Boolean, nullable=False, default=False)
    # 允许访问的菜单key，逗号分隔；is_super 时忽略此字段(全部可见)
    allowed_menus = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
