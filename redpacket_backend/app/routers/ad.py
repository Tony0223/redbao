from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/ad", tags=["ad"])


@router.post("/reward", response_model=schemas.AdRewardResponse)
def report_ad_watch(
    payload: schemas.AdRewardRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    App看完一次广告后上报，服务器按规则算出金币数并发放，返回结果给App显示。
    看广告的是谁，从请求头的token解析，不再相信客户端自己传的user_id
    （不然任何人随便传个数字就能冒充别人白嫖金币）。
    """
    return crud.calculate_ad_reward(
        db=db, user=current_user, ad_type=payload.ad_type, is_game_ad=payload.is_game_ad
    )
