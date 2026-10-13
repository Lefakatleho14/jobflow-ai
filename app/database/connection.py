"""
SQLAlchemy engine and session factory.

Reads DATABASE_PATH from the environment (see .env.example).
Enables SQLite foreign-key enforcement per connection.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# ---- Load .env once at import time ----
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


def _database_url() -> str:
    """Build the SQLAlchemy URL from DATABASE_PATH."""
    raw_path = os.getenv("DATABASE_PATH", "./data/app.db")
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = _database_url()

# ---- Engine ----
# `check_same_thread=False` is required because FastAPI/APScheduler may
# hand the same connection to different threads. SQLite itself is
# thread-safe in serialized mode; SQLAlchemy manages the pool.
engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """SQLite disables foreign keys by default. Turn them on per connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


# ---- Session factory ----
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Context manager that yields a Session, commits on success,
    rolls back on exception, and always closes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """
    FastAPI-style dependency. Yields a session and closes it.
    Routes that need to write should commit explicitly.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()