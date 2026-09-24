"""
微信登录：拿App端传来的临时code，去微信服务器换真正的openid，顺便取昵称和头像。

两步：
1. sns/oauth2/access_token  —— code 换 openid + access_token（只有这三个字段，没有昵称头像）
2. sns/userinfo             —— 用上一步的 access_token + openid 换昵称和头像

第2步是【尽力而为】：微信那边偶尔抽风或者用户授权范围不够时拿不到，
这种情况下只记个日志，照样用第1步的结果让用户登录成功。
总不能因为拿不到头像就让人登不进来。

文档：https://developers.weixin.qq.com/doc/oplatform/Mobile_App/WeChat_Login/Authorized_API_call_UnionID.html
"""
import logging
import os

import httpx

logger = logging.getLogger("wechat")

WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")

WECHAT_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


class WeChatLoginError(Exception):
    """微信接口返回了errcode，说明code无效/过期/appsecret不对之类的问题。"""
    pass


def fetch_user_info(access_token: str, openid: str) -> dict:
    """
    取微信昵称和头像。拿不到就返回空字典，不抛异常——这一步失败不该影响登录。

    返回里我们只关心 nickname 和 headimgurl。
    headimgurl 末尾的数字是尺寸，0 表示640x640原图，46/64/96/132 是各种小尺寸。
    这里把它换成 132，头像框就几十dp，下原图纯属浪费流量。
    """
    if not access_token or not openid:
        return {}

    try:
        resp = httpx.get(
            WECHAT_USERINFO_URL,
            params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
            timeout=8,
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("取微信用户信息失败（不影响登录）: %s", e)
        return {}

    if "errcode" in data:
        logger.warning("取微信用户信息返回错误（不影响登录）: %s %s",
                       data.get("errcode"), data.get("errmsg"))
        return {}

    avatar = (data.get("headimgurl") or "").strip()
    if avatar.endswith("/0"):
        avatar = avatar[:-1] + "132"   # 换成132x132，省流量

    return {
        "nickname": (data.get("nickname") or "").strip(),
        "avatar_url": avatar,
    }


def exchange_code_for_openid(code: str) -> dict:
    """
    拿App端传来的code换openid，顺带取昵称和头像。

    返回 {"openid": ..., "access_token": ..., "unionid": ...(可能没有),
          "nickname": ...(可能为空), "avatar_url": ...(可能为空)}

    换失败（code过期、appid/secret不对等）会抛 WeChatLoginError，
    调用方接住之后应该给App返回一个清晰的错误提示，而不是让用户看到500。
    """
    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        raise WeChatLoginError("服务端还没配置微信AppID/AppSecret，请联系管理员")

    params = {
        "appid": WECHAT_APP_ID,
        "secret": WECHAT_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    try:
        resp = httpx.get(WECHAT_ACCESS_TOKEN_URL, params=params, timeout=10)
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise WeChatLoginError(f"请求微信接口失败: {e}")

    if "errcode" in data:
        raise WeChatLoginError(f"微信登录失败: {data.get('errcode')} {data.get('errmsg')}")

    if "openid" not in data:
        raise WeChatLoginError("微信接口返回异常，没有拿到openid")

    # 第二步：取昵称头像。失败也不影响登录，所以不抛异常。
    info = fetch_user_info(data.get("access_token", ""), data["openid"])
    data.update(info)
    return data
