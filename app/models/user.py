"""
User, Profile, Skill, Project ORM models.
"""

from __future__ import annotations

import json
from typing import Any, List

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _to_json_list(value: Any) -> str:
    """Serialize a list (or None) to a JSON string for storage."""
    if value is None:
        return "[]"
    return json.dumps(list(value))


def _from_json_list(value: str | None) -> List[Any]:
    """Deserialize a JSON string to a list."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Identity / education
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    education: Mapped[str | None] = mapped_column(String(255), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Stack — stored as JSON lists of strings
    languages_json: Mapped[str] = mapped_column("languages", Text, default="[]")
    frameworks_json: Mapped[str] = mapped_column("frameworks", Text, default="[]")
    databases_json: Mapped[str] = mapped_column("databases", Text, default="[]")
    cloud_json: Mapped[str] = mapped_column("cloud", Text, default="[]")
    devops_json: Mapped[str] = mapped_column("devops", Text, default="[]")
    tools_json: Mapped[str] = mapped_column("tools", Text, default="[]")
    certifications_json: Mapped[str] = mapped_column("certifications", Text, default="[]")

    # Preferences
    preferred_titles_json: Mapped[str] = mapped_column("preferred_titles", Text, default="[]")
    preferred_locations_json: Mapped[str] = mapped_column("preferred_locations", Text, default="[]")
    remote_preference: Mapped[str] = mapped_column(String(20), default="any")
    minimum_match_score: Mapped[int] = mapped_column(Integer, default=70)

    experience_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )

    # ---- Convenience accessors for JSON columns ----
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
    def tools(self) -> list[str]:
        return _from_json_list(self.tools_json)

    @tools.setter
    def tools(self, value: list[str]) -> None:
        self.tools_json = _to_json_list(value)

    @property
    def certifications(self) -> list[str]:
        return _from_json_list(self.certifications_json)

    @certifications.setter
    def certifications(self, value: list[str]) -> None:
        self.certifications_json = _to_json_list(value)

    @property
    def preferred_titles(self) -> list[str]:
        return _from_json_list(self.preferred_titles_json)

    @preferred_titles.setter
    def preferred_titles(self, value: list[str]) -> None:
        self.preferred_titles_json = _to_json_list(value)

    @property
    def preferred_locations(self) -> list[str]:
        return _from_json_list(self.preferred_locations_json)

    @preferred_locations.setter
    def preferred_locations(self, value: list[str]) -> None:
        self.preferred_locations_json = _to_json_list(value)


class Skill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_skill_profile_name"),
    )

    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="other")
    proficiency: Mapped[str] = mapped_column(String(20), default="intermediate")
    years: Mapped[float | None] = mapped_column(nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="skills")


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technologies_json: Mapped[str] = mapped_column("technologies", Text, default="[]")
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="projects")

    @property
    def technologies(self) -> list[str]:
        return _from_json_list(self.technologies_json)

    @technologies.setter
    def technologies(self, value: list[str]) -> None:
        self.technologies_json = _to_json_list(value)