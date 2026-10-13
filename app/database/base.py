"""
Declarative base and shared mixins for all ORM models.

We use SQLAlchemy 2.0 style (`Mapped[...]`, `mapped_column`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    """Return a new UUID4 as a 36-character string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Common declarative base for every model in the project."""
    pass


class UUIDPrimaryKeyMixin:
    """Adds a string UUID primary key column named `id`."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )


class TimestampMixin:
    """Adds `created_at` and `updated_at` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )