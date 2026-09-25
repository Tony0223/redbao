import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import crud, punch_service
from app.database import Base, SessionLocal, engine
from app.routers import (
    ad, admin, admin_punch, admin_signin, admin_subsidy, invite, landing,
    punch, subsidy, user, welfare, withdrawal,
)

from app import bonus_models, wheel_models   # noqa: F401  让 create_all 认识新表
from app.routers import admin_bonus, admin_wheel, bonus, wheel

from app import coin_models                       # noqa: F401  让 create_all 认识 coin_logs 表
from app.routers import admin_content, mine

from app import feedback_models                      # noqa: F401
from app.routers import admin_feedback, feedback

logger = logging.getLogger("main")

# 启动时自动建表（表已存在则跳过）。
Base.metadata.create_all(bind=engine)

# 启动时把预置的设置项缺的补上默认值，并确保存在超管后台账号
from app.routers.admin import ADMIN_USERNAME, ADMIN_PASSWORD  # noqa: E402

_startup_db = SessionLocal()
try:
    crud.ensure_default_settings(_startup_db)
    crud.ensure_super_admin(_startup_db, ADMIN_USERNAME, ADMIN_PASSWORD)
finally:
    _startup_db.close()

app = FastAPI(
    title="红包群后台API",
    description="负责金币奖励规则计算、用户余额、提现等服务端逻辑",
    version="0.1.0",
)

# 静态资源(App图标等)，落地页 /static/app_icon.png 用
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(user.router)
app.include_router(ad.router)
app.include_router(admin.router)
app.include_router(admin_punch.router)
app.include_router(admin_signin.router)
app.include_router(admin_subsidy.router)
app.include_router(withdrawal.router)
app.include_router(invite.router)
app.include_router(subsidy.router)
app.include_router(welfare.router)
app.include_router(punch.router)
app.include_router(landing.router)
app.include_router(bonus.router)
app.include_router(wheel.router)
app.include_router(admin_bonus.router)
app.include_router(admin_wheel.router)
app.include_router(mine.router)
app.include_router(admin_content.router)
app.include_router(feedback.router)
app.include_router(admin_feedback.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# ====================== 定时任务 ======================
# 每分钟检查一次：到了开奖时间就给今天的打卡开奖。
# publish() 本身是幂等的，重复调用不会重复发钱。

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _publish_punch_job():
    db = SessionLocal()
    try:
        punch_service.publish_if_due(db)
    except Exception as e:
        logger.error("打卡开奖任务出错: %s", e)
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(_publish_punch_job, "interval", minutes=1, id="punch_publish",
                      replace_existing=True)
    scheduler.start()
    logger.info("定时任务已启动")


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown(wait=False)