from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas, wechat
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/user", tags=["user"])


@router.post("/login", response_model=schemas.UserCreateResponse)
def login_or_create(payload: schemas.UserCreateRequest, db: Session = Depends(get_db)):
    """
    正式登录：App传微信登录SDK拿到的code，这里换真实openid，
    再用openid查/建用户——用户身份完全由服务端向微信验证过，客户端没法伪造。

    仍然保留openid直传这条路径，只是仅供开发调试用，不应该在正式发布的App里触发。

    登录成功（不管新用户还是老用户）都会生成一个新token返回给App，
    App把这个token存起来，之后每次请求都带着它，不再是自己声明user_id。

    inviter_code：App从邀请落地页写入的剪贴板口令里读到的邀请码，
    只在新用户注册这一次绑定邀请关系；老用户再次登录不会改绑（防止刷邀请）。

    昵称和头像：每次登录都用微信返回的最新值覆盖本地的。
    用户在微信里换了头像或昵称，下次进App就跟着更新了。
    微信那边没取到（userinfo 调用失败）时保留原值，不会把已有的清空。
    """
    if not payload.code and not payload.openid:
        raise HTTPException(status_code=400, detail="code和openid必须传一个")

    avatar_url = ""
    if payload.code:
        try:
            wechat_data = wechat.exchange_code_for_openid(payload.code)
        except wechat.WeChatLoginError as e:
            raise HTTPException(status_code=400, detail=str(e))
        openid = wechat_data["openid"]
        # 微信返回里有昵称就用微信的，没有再退回客户端传的
        nickname = wechat_data.get("nickname") or payload.nickname
        avatar_url = wechat_data.get("avatar_url") or ""
    else:
        openid = payload.openid
        nickname = payload.nickname

    existing = crud.get_user_by_openid(db, openid)
    if existing:
        # 老用户：昵称头像跟着微信更新，邀请关系不动
        changed = False
        if nickname and existing.nickname != nickname:
            existing.nickname = nickname
            changed = True
        if avatar_url and existing.avatar_url != avatar_url:
            existing.avatar_url = avatar_url
            changed = True
        if changed:
            db.add(existing)
            db.commit()
        token = crud.issue_login_token(db, existing)
        return schemas.UserCreateResponse(
            user_id=existing.id,
            is_new_user=False,
            coin_balance=existing.coin_balance,
            invite_code=existing.invite_code,
            token=token,
        )

    user = crud.create_user(
        db, openid=openid, nickname=nickname, inviter_code=payload.inviter_code,
        avatar_url=avatar_url,
    )
    token = crud.issue_login_token(db, user)
    return schemas.UserCreateResponse(
        user_id=user.id,
        is_new_user=True,
        coin_balance=user.coin_balance,
        invite_code=user.invite_code,
        token=token,
    )


@router.post("/logout")
def logout(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """退出登录：清空服务端记的token，旧token之后请求全部会被401拒绝。"""
    crud.clear_token(db, current_user)
    return {"success": True}


@router.get("/me/balance", response_model=schemas.UserBalanceResponse)
def get_my_balance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """查自己的余额，身份从token解析，不能再传别人的user_id来查。"""
    return schemas.UserBalanceResponse(
        user_id=current_user.id,
        coin_balance=current_user.coin_balance,
        ad_watch_count=current_user.ad_watch_count,
        tier=current_user.tier,
    )
