"""
数据库连接配置。
所有连接参数从环境变量读取，部署时把 .env.example 复制成 .env 并填真实值。
"""
from dotenv import load_dotenv 
load_dotenv() 
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "redpacket")

# 用 pymysql 驱动；宝塔面板装的MySQL默认兼容
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # 自动检测断线重连，避免MySQL超时把连接踢掉导致报错
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI依赖注入用：每个请求开一个数据库会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
