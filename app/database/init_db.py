"""
Database initializer.

`create_tables()` — idempotent; creates tables if missing.
`reset_database()` — destructive; drops everything and recreates.

Importing `app.models` is REQUIRED before calling create_all so that
every model is registered on Base.metadata.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect

# These imports have side effects (model registration). Do not remove.
from app import models  # noqa: F401
from app.database.base import Base
from app.database.connection import engine

logger = logging.getLogger(__name__)


def create_tables() -> None:
    """Create all tables. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def list_tables() -> list[str]:
    """Return table names currently present in the database."""
    inspector = inspect(engine)
    return sorted(inspector.get_table_names())


def reset_database() -> None:
    """Drop every table and recreate. DESTRUCTIVE."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def database_is_initialized() -> bool:
    """Return True if all expected tables exist."""
    expected = set(Base.metadata.tables.keys())
    present = set(list_tables())
    return expected.issubset(present)