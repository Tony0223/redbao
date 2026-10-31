"""Database engine and session management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def build_database_url():
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return make_url(configured_url)

    return URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("MYSQL_USER", "quiz_app"),
        password=os.getenv("MYSQL_PASSWORD", "change_me"),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "quiz_app"),
        query={"charset": "utf8mb4"},
    )


def create_database_engine() -> Engine:
    database_url = build_database_url()
    options = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    # SQLite is only supported as a lightweight test database. Production uses MySQL.
    if database_url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        if database_url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool

    return create_engine(database_url, **options)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create model tables for isolated tests; production schema uses Alembic."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
