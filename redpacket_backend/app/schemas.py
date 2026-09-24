"""
API请求/响应的数据结构（Pydantic模型）。
FastAPI用这些自动生成接口文档、自动做参数校验。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import AdType, UserTier


class AdRewardRequest(BaseModel):
    """
    App看完广告后上报，请求发放金币。
    不再传user_id——用户身份从请求头的token解析，不相信客户端自己声明的身份。
    """
    ad_type: AdType
    is_game_ad: bool = False


class AdRewardResponse(BaseModel):
    """服务器算好金币后返回给App。"""
    reward_amount: int       # 这次基础奖励拿到多少金币
    bonus_amount: int        # 这次是否触发了赐福，触发了是多少
    total_this_time: int     # reward_amount + bonus_amount，App直接拿这个数字弹提示就行
    new_balance: int         # 用户当前总金币余额
    ad_watch_count: int      # 用户累计看了多少个广告（方便App显示"再看N个广告有赐福"之类的提示）

    class Config:
        from_attributes = True


class UserBalanceResponse(BaseModel):
    user_id: int
    coin_balance: int
    ad_watch_count: int
    tier: UserTier

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    """
    创建/登录用户。
    正式方式：App传微信登录SDK拿到的 code，服务端拿AppSecret去微信接口换真实openid。
    临时测试方式：直接传openid字符串（仅供开发调试用，不安全，不应该在生产环境依赖这条路径）。
    """
    code: Optional[str] = None       # 微信登录拿到的临时code，正式登录走这个
    openid: Optional[str] = None     # 仅供开发测试直接指定openid，微信登录接入后不应该再用
    nickname: Optional[str] = None
    inviter_code: Optional[str] = None  # 如果是通过别人的邀请链接/邀请码进来的，传这个


class UserCreateResponse(BaseModel):
    user_id: int
    is_new_user: bool
    coin_balance: int
    invite_code: str  # 这个新用户自己的邀请码，App里"邀请好友"页面要用来生成分享链接
    token: str         # 登录令牌，App要存下来，之后每次请求带在Authorization头里

    class Config:
        from_attributes = True


class WithdrawalRequestCreate(BaseModel):
    """不再传user_id——用户身份从请求头的token解析。"""
    coin_amount: int


class WithdrawalRequestResponse(BaseModel):
    id: int
    coin_amount: int
    yuan_amount: int  # 单位：分
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class WithdrawalListItem(BaseModel):
    """提现记录列表的单条。金额元由后端算好给App，避免两端汇率不一致。"""
    id: int
    coin_amount: int
    yuan_amount: int          # 单位：分
    status: str               # pending/processing/success/failed
    status_text: str          # 中文，App直接显示
    created_at: str           # 已格式化 "2026-09-19 14:30:00"

    class Config:
        from_attributes = True
