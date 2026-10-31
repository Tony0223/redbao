"""答题 APP 后端。

运行方式：uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database import check_database, db_session
from models import AuthSession, QuizResult, User


APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Shanghai"))
SESSION_DAYS = 30
PASSWORD_ITERATIONS = 210_000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{2,20}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PRIVACY_POLICY_FILE = Path(__file__).with_name("privacy_policy.html")
USER_AGREEMENT_FILE = Path(__file__).with_name("user_agreement.html")


TOPICS = [
    {
        "id": "daily",
        "name": "每日挑战",
        "description": "每天 5 道精选题，保持学习状态",
        "icon": "⚡",
        "color": "#7c5cff",
    },
    {
        "id": "python",
        "name": "Python 基础",
        "description": "语法、数据结构与常用知识",
        "icon": "🐍",
        "color": "#36b8a4",
    },
    {
        "id": "frontend",
        "name": "前端知识",
        "description": "HTML、CSS、JavaScript 与 Vue",
        "icon": "💻",
        "color": "#ff8a5b",
    },
]


QUESTIONS = [
    {
        "id": 1,
        "topic_id": "daily",
        "type": "single",
        "title": "中国最大的淡水湖是哪一个？",
        "options": ["洞庭湖", "鄱阳湖", "太湖", "洪泽湖"],
        "answer": 1,
        "explanation": "鄱阳湖位于江西省，是中国第一大淡水湖。",
    },
    {
        "id": 2,
        "topic_id": "daily",
        "type": "single",
        "title": "一年中，北半球白昼最长的一天通常是？",
        "options": ["春分", "夏至", "秋分", "冬至"],
        "answer": 1,
        "explanation": "夏至时太阳直射北回归线，北半球白昼达到全年最长。",
    },
    {
        "id": 3,
        "topic_id": "daily",
        "type": "single",
        "title": "被称为“计算机之父”的科学家是？",
        "options": ["图灵", "冯·诺依曼", "查尔斯·巴贝奇", "香农"],
        "answer": 2,
        "explanation": "查尔斯·巴贝奇设计了差分机和分析机，常被称为计算机之父。",
    },
    {
        "id": 4,
        "topic_id": "daily",
        "type": "single",
        "title": "人体内负责输送氧气的血细胞是？",
        "options": ["白细胞", "血小板", "红细胞", "淋巴细胞"],
        "answer": 2,
        "explanation": "红细胞中的血红蛋白能够与氧结合并将其输送到全身。",
    },
    {
        "id": 5,
        "topic_id": "daily",
        "type": "single",
        "title": "《兰亭集序》的作者是谁？",
        "options": ["王羲之", "颜真卿", "柳公权", "欧阳询"],
        "answer": 0,
        "explanation": "《兰亭集序》由东晋书法家王羲之所作，被誉为“天下第一行书”。",
    },
    {
        "id": 101,
        "topic_id": "python",
        "type": "single",
        "title": "Python 中哪种数据类型是不可变的？",
        "options": ["list", "dict", "set", "tuple"],
        "answer": 3,
        "explanation": "tuple（元组）创建后不能修改其中的元素，属于不可变类型。",
    },
    {
        "id": 102,
        "topic_id": "python",
        "type": "single",
        "title": "表达式 len({'a': 1, 'b': 2}) 的结果是？",
        "options": ["1", "2", "3", "报错"],
        "answer": 1,
        "explanation": "len(dict) 返回字典键值对的数量，这个字典有两个键。",
    },
    {
        "id": 103,
        "topic_id": "python",
        "type": "single",
        "title": "用于定义 Python 函数的关键字是？",
        "options": ["func", "function", "def", "lambda"],
        "answer": 2,
        "explanation": "普通命名函数使用 def 关键字定义；lambda 用于匿名函数。",
    },
    {
        "id": 104,
        "topic_id": "python",
        "type": "single",
        "title": "下面哪个写法可以捕获异常？",
        "options": ["if / else", "try / except", "for / in", "with / as"],
        "answer": 1,
        "explanation": "Python 使用 try / except 结构捕获并处理异常。",
    },
    {
        "id": 105,
        "topic_id": "python",
        "type": "single",
        "title": "列表推导式 [x * 2 for x in range(3)] 的结果是？",
        "options": ["[0, 1, 2]", "[2, 4, 6]", "[0, 2, 4]", "[1, 2, 3]"],
        "answer": 2,
        "explanation": "range(3) 产生 0、1、2，分别乘 2 后为 [0, 2, 4]。",
    },
    {
        "id": 201,
        "topic_id": "frontend",
        "type": "single",
        "title": "CSS 中用于创建弹性布局的属性值是？",
        "options": ["display: flex", "position: flex", "layout: flex", "float: flex"],
        "answer": 0,
        "explanation": "在容器上设置 display: flex，即可启用 Flex 弹性布局。",
    },
    {
        "id": 202,
        "topic_id": "frontend",
        "type": "single",
        "title": "Vue 2 中组件的 data 选项通常应该是什么？",
        "options": ["数组", "函数", "字符串", "Promise"],
        "answer": 1,
        "explanation": "组件的 data 应当是返回对象的函数，避免多个实例共享同一个数据对象。",
    },
    {
        "id": 203,
        "topic_id": "frontend",
        "type": "single",
        "title": "JavaScript 严格相等运算符是？",
        "options": ["=", "==", "===", "!="],
        "answer": 2,
        "explanation": "=== 会同时比较值和类型，不进行隐式类型转换。",
    },
    {
        "id": 204,
        "topic_id": "frontend",
        "type": "single",
        "title": "uni-app 中发起网络请求使用哪个 API？",
        "options": ["uni.fetch", "uni.request", "uni.ajax", "uni.http"],
        "answer": 1,
        "explanation": "uni.request 是 uni-app 提供的跨端网络请求 API。",
    },
    {
        "id": 205,
        "topic_id": "frontend",
        "type": "single",
        "title": "HTML 中语义化表示页面主内容的标签是？",
        "options": ["<div>", "<span>", "<main>", "<aside>"],
        "answer": 2,
        "explanation": "<main> 用于表示文档中主要且独有的内容。",
    },
]


class AnswerRequest(BaseModel):
    question_id: int
    answer: int = Field(ge=0)


class ResultRequest(BaseModel):
    topic_id: str
    correct_count: int = Field(ge=0)
    total_count: int = Field(gt=0)
    duration_seconds: int = Field(ge=0)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    account: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=72)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=8, max_length=72)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    check_database()
    yield


def configured_cors_origins() -> List[str]:
    value = os.getenv("CORS_ORIGINS", "*")
    return [item.strip() for item in value.split(",") if item.strip()]


app = FastAPI(title="答题星球 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_question(question: Dict) -> Dict:
    return {
        "id": question["id"],
        "type": question["type"],
        "title": question["title"],
        "options": question["options"],
    }


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def password_matches(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (TypeError, ValueError):
        return False


def user_payload(user: User) -> Dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": f"{user.created_at.isoformat()}Z",
    }


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    return token.strip()


def current_user(authorization: Optional[str], required: bool = False) -> Optional[User]:
    token = bearer_token(authorization)
    if not token:
        if required:
            raise HTTPException(status_code=401, detail="请先登录")
        return None

    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_session() as session:
        user = session.scalar(
            select(User)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(
                AuthSession.token_hash == token_digest,
                AuthSession.expires_at > now,
            )
        )
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return user


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_session() as session:
        session.add(
            AuthSession(
                user_id=user_id,
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                created_at=now,
                expires_at=now + timedelta(days=SESSION_DAYS),
            )
        )
    return token


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "答题星球 API 正在运行"}


@app.get("/privacy", response_class=FileResponse, include_in_schema=False)
def privacy_policy() -> FileResponse:
    return FileResponse(PRIVACY_POLICY_FILE, media_type="text/html; charset=utf-8")


@app.get("/agreement", response_class=FileResponse, include_in_schema=False)
def user_agreement() -> FileResponse:
    return FileResponse(USER_AGREEMENT_FILE, media_type="text/html; charset=utf-8")


@app.get("/health", include_in_schema=False)
def health() -> Dict[str, str]:
    try:
        check_database()
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="数据库连接不可用") from error
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest) -> Dict:
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=422, detail="用户名需为 2-20 位中文、字母、数字或下划线"
        )
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="请输入有效的邮箱地址")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        with db_session() as session:
            existing = session.scalar(
                select(User).where(
                    (func.lower(User.username) == username.lower())
                    | (func.lower(User.email) == email)
                )
            )
            if existing:
                message = "该邮箱已注册" if existing.email.lower() == email else "用户名已存在"
                raise HTTPException(status_code=409, detail=message)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash(payload.password),
                created_at=now,
            )
            session.add(user)
            session.flush()
            response_user = user_payload(user)
            user_id = user.id
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="用户名或邮箱已被使用") from error

    return {"token": create_session(user_id), "user": response_user}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Dict:
    account = payload.account.strip().lower()
    with db_session() as session:
        user = session.scalar(
            select(User).where(
                (func.lower(User.username) == account)
                | (func.lower(User.email) == account)
            )
        )
    if not user or not password_matches(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {"token": create_session(user.id), "user": user_payload(user)}


@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = Header(default=None)) -> Dict:
    return {"user": user_payload(current_user(authorization, required=True))}


@app.post("/api/auth/logout", status_code=204, response_class=Response)
def logout(authorization: Optional[str] = Header(default=None)):
    current_user(authorization, required=True)
    token = bearer_token(authorization)
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with db_session() as session:
        auth_session = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_digest)
        )
        if auth_session:
            session.delete(auth_session)
    return Response(status_code=204)


@app.delete("/api/auth/account", status_code=204, response_class=Response)
def delete_account(
    payload: DeleteAccountRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = current_user(authorization, required=True)
    if not password_matches(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误，无法注销账号")

    with db_session() as session:
        stored_user = session.get(User, user.id)
        if not stored_user:
            raise HTTPException(status_code=401, detail="账号不存在或已注销")
        # 主动清理全部登录会话和学习记录，避免依赖不同数据库的外键策略。
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.execute(delete(QuizResult).where(QuizResult.user_id == user.id))
        session.delete(stored_user)
    return Response(status_code=204)


@app.get("/api/topics")
def get_topics() -> Dict[str, List[Dict]]:
    items = []
    for topic in TOPICS:
        count = sum(question["topic_id"] == topic["id"] for question in QUESTIONS)
        items.append({**topic, "question_count": count})
    return {"items": items}


@app.get("/api/topics/{topic_id}/questions")
def get_questions(
    topic_id: str,
    limit: int = Query(default=5, ge=1, le=20),
) -> Dict:
    topic = next((item for item in TOPICS if item["id"] == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="题库不存在")

    questions = [item for item in QUESTIONS if item["topic_id"] == topic_id]
    return {
        "topic": topic,
        "items": [public_question(item) for item in questions[:limit]],
    }


@app.post("/api/answers")
def check_answer(payload: AnswerRequest) -> Dict:
    question = next((item for item in QUESTIONS if item["id"] == payload.question_id), None)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    if payload.answer >= len(question["options"]):
        raise HTTPException(status_code=422, detail="选项无效")

    return {
        "correct": payload.answer == question["answer"],
        "correct_answer": question["answer"],
        "explanation": question["explanation"],
    }


@app.post("/api/results", status_code=201)
def save_result(
    payload: ResultRequest,
    authorization: Optional[str] = Header(default=None),
) -> Dict:
    if payload.correct_count > payload.total_count:
        raise HTTPException(status_code=422, detail="答对数不能大于总题数")
    if not any(item["id"] == payload.topic_id for item in TOPICS):
        raise HTTPException(status_code=404, detail="题库不存在")

    user = current_user(authorization)
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_session() as session:
        result = QuizResult(
            user_id=user.id if user else None,
            topic_id=payload.topic_id,
            correct_count=payload.correct_count,
            total_count=payload.total_count,
            duration_seconds=payload.duration_seconds,
            created_at=created_at,
        )
        session.add(result)
        session.flush()
        result_id = result.id
    return {"id": result_id, "created_at": f"{created_at.isoformat()}Z"}


@app.get("/api/stats")
def get_stats(authorization: Optional[str] = Header(default=None)) -> Dict:
    user = current_user(authorization)
    now_local = datetime.now(APP_TIMEZONE)
    today_start_local = datetime.combine(now_local.date(), time.min, APP_TIMEZONE)
    tomorrow_start_local = datetime.combine(
        now_local.date() + timedelta(days=1),
        time.min,
        APP_TIMEZONE,
    )
    today_start_utc = today_start_local.astimezone(timezone.utc).replace(tzinfo=None)
    tomorrow_start_utc = tomorrow_start_local.astimezone(timezone.utc).replace(tzinfo=None)

    owner_condition = (
        QuizResult.user_id == user.id if user else QuizResult.user_id.is_(None)
    )
    with db_session() as session:
        summary = session.execute(
            select(
                func.count(QuizResult.id).label("completed"),
                func.coalesce(func.sum(QuizResult.correct_count), 0).label("correct"),
                func.coalesce(func.sum(QuizResult.total_count), 0).label("total"),
            ).where(owner_condition)
        ).one()
        today_count = session.scalar(
            select(func.count(QuizResult.id)).where(
                owner_condition,
                QuizResult.created_at >= today_start_utc,
                QuizResult.created_at < tomorrow_start_utc,
            )
        )

    accuracy = round(summary.correct * 100 / summary.total) if summary.total else 0
    return {
        "completed": summary.completed,
        "accuracy": accuracy,
        "today_completed": bool(today_count),
    }
