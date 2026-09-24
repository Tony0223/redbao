"""
简单的token身份验证。

App登录成功后拿到一个token，之后每次请求在HTTP头里带：
    Authorization: Bearer <token>

这个依赖负责从请求头里把token解出来、查出对应用户，
查不到或者没带就直接401——不再相信客户端自己说"我是user_id=123"这种裸传法，
不然任何人随便传个数字就能冒充别人看广告拿钱、甚至申请提现。
"""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, models
from app.database import get_db


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少登录凭证，请先登录",
        )

    token = authorization[len("Bearer "):].strip()
    user = crud.get_user_by_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
        )
    return user
