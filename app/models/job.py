"""
Job, JobRequirement, JobMatch ORM models.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _to_json_list(value: Any) -> str:
    if value is None:
        return "[]"
    return json.dumps(list(value))


def _from_json_list(value: str | None) -> List[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_company", "company"),
        Index("ix_jobs_title", "title"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_date_found", "date_found"),
        Index("ix_jobs_content_hash", "content_hash"),
    )

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remote_status: Mapped[str] = mapped_column(String(20), default="unknown")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    date_found: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_posted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="discovered")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    requirement: Mapped["JobRequirement | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    match: Mapped["JobMatch | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    application: Mapped["Application | None"] = relationship(  # noqa: F821
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

    aliases: Mapped[list["JobAlias"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobRequirement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_requirements"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)

    languages_json: Mapped[str] = mapped_column("languages", Text, default="[]")
    frameworks_json: Mapped[str] = mapped_column("frameworks", Text, default="[]")
    databases_json: Mapped[str] = mapped_column("databases", Text, default="[]")
    cloud_json: Mapped[str] = mapped_column("cloud", Text, default="[]")
    devops_json: Mapped[str] = mapped_column("devops", Text, default="[]")
    soft_skills_json: Mapped[str] = mapped_column("soft_skills", Text, default="[]")
    education_json: Mapped[str] = mapped_column("education", Text, default="[]")

    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="requirement")

    # ---- JSON helpers ----
    @property
    def languages(self) -> list[str]:
        return _from_json_list(self.languages_json)

    @languages.setter
    def languages(self, value: list[str]) -> None:
        self.languages_json = _to_json_list(value)

    @property
    def frameworks(self) -> list[str]:
        return _from_json_list(self.frameworks_json)

    @frameworks.setter
    def frameworks(self, value: list[str]) -> None:
        self.frameworks_json = _to_json_list(value)

    @property
    def databases(self) -> list[str]:
        return _from_json_list(self.databases_json)

    @databases.setter
    def databases(self, value: list[str]) -> None:
        self.databases_json = _to_json_list(value)

    @property
    def cloud(self) -> list[str]:
        return _from_json_list(self.cloud_json)

    @cloud.setter
    def cloud(self, value: list[str]) -> None:
        self.cloud_json = _to_json_list(value)

    @property
    def devops(self) -> list[str]:
        return _from_json_list(self.devops_json)

    @devops.setter
    def devops(self, value: list[str]) -> None:
        self.devops_json = _to_json_list(value)

    @property
    def soft_skills(self) -> list[str]:
        return _from_json_list(self.soft_skills_json)

    @soft_skills.setter
    def soft_skills(self, value: list[str]) -> None:
        self.soft_skills_json = _to_json_list(value)

    @property
    def education(self) -> list[str]:
        return _from_json_list(self.education_json)

    @education.setter
    def education(self, value: list[str]) -> None:
        self.education_json = _to_json_list(value)


class JobMatch(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_matches"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )

    score: Mapped[float] = mapped_column(default=0.0)
    tier: Mapped[str] = mapped_column(String(10), default="low")

    technical_score: Mapped[float] = mapped_column(default=0.0)
    education_score: Mapped[float] = mapped_column(default=0.0)
    experience_score: Mapped[float] = mapped_column(default=0.0)
    projects_score: Mapped[float] = mapped_column(default=0.0)
    location_score: Mapped[float] = mapped_column(default=0.0)
    other_score: Mapped[float] = mapped_column(default=0.0)

    strong_matches_json: Mapped[str] = mapped_column("strong_matches", Text, default="[]")
    partial_matches_json: Mapped[str] = mapped_column("partial_matches", Text, default="[]")
    missing_skills_json: Mapped[str] = mapped_column("missing_skills", Text, default="[]")

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="match")

    @property
    def strong_matches(self) -> list[str]:
        return _from_json_list(self.strong_matches_json)

    @strong_matches.setter
    def strong_matches(self, value: list[str]) -> None:
        self.strong_matches_json = _to_json_list(value)

    @property
    def partial_matches(self) -> list[str]:
        return _from_json_list(self.partial_matches_json)

    @partial_matches.setter
    def partial_matches(self, value: list[str]) -> None:
        self.partial_matches_json = _to_json_list(value)

    @property
    def missing_skills(self) -> list[str]:
        return _from_json_list(self.missing_skills_json)

    @missing_skills.setter
    def missing_skills(self, value: list[str]) -> None:
        self.missing_skills_json = _to_json_list(value)