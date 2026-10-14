"""
JobAlias — an advisory link from a rejected payload to an existing job.

Fuzzy matches do not merge or delete anything. They record the fact
that a payload *looked like* an existing job, so the user can review.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_aliases"
    __table_args__ = (
        UniqueConstraint("job_id", "alias_hash", name="uq_alias_job_hash"),
    )

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )

    alias_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    alias_title: Mapped[str] = mapped_column(String(300), nullable=False)
    alias_company: Mapped[str] = mapped_column(String(200), nullable=False)
    alias_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    alias_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    alias_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    similarity: Mapped[float] = mapped_column(default=0.0)
    title_similarity: Mapped[float] = mapped_column(default=0.0)
    location_similarity: Mapped[float] = mapped_column(default=0.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="aliases")  # noqa: F821