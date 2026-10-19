"""
ProjectService — CRUD for projects on the local profile.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project
from app.services.profile.errors import ProfileError
from app.services.profile.service import ProfileService

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str | None, field: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if not _DATE_RE.match(text):
        raise ProfileError(f"{field} must be ISO date (YYYY-MM-DD), got {text!r}")
    return text


class ProjectService:
    def __init__(self, session: Session):
        self.session = session

    def list_projects(self) -> list[Project]:
        profile = ProfileService(self.session).ensure_profile()
        stmt = (
            select(Project)
            .where(Project.profile_id == profile.id)
            .order_by(Project.name)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_project(self, name: str) -> Project | None:
        profile = ProfileService(self.session).ensure_profile()
        stmt = select(Project).where(
            Project.profile_id == profile.id,
            Project.name == name.strip(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def add_project(
        self,
        name: str,
        *,
        description: str | None = None,
        technologies: list[str] | None = None,
        role: str | None = None,
        url: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Project:
        cleaned_name = str(name).strip()
        if not cleaned_name:
            raise ProfileError("project name cannot be empty")

        techs = [str(t).strip() for t in (technologies or []) if str(t).strip()]
        # Deduplicate preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for t in techs:
            k = t.lower()
            if k not in seen:
                seen.add(k)
                deduped.append(t)

        start = _validate_date(start_date, "start_date")
        end = _validate_date(end_date, "end_date")
        if start and end and start > end:
            raise ProfileError("start_date cannot be after end_date")

        profile = ProfileService(self.session).ensure_profile()

        existing = self.get_project(cleaned_name)
        if existing is not None:
            existing.description = description
            existing.technologies = deduped
            existing.role = role
            existing.url = url
            existing.start_date = start
            existing.end_date = end
            self.session.flush()
            logger.info("Updated project: %s", cleaned_name)
            return existing

        project = Project(
            profile_id=profile.id,
            name=cleaned_name,
            description=description,
            role=role,
            url=url,
            start_date=start,
            end_date=end,
        )
        project.technologies = deduped
        self.session.add(project)
        self.session.flush()
        logger.info("Added project: %s", cleaned_name)
        return project

    def remove_project(self, name: str) -> bool:
        project = self.get_project(name)
        if project is None:
            return False
        self.session.delete(project)
        self.session.flush()
        return True

    def clear(self) -> int:
        profile = ProfileService(self.session).ensure_profile()
        stmt = select(Project).where(Project.profile_id == profile.id)
        projects = list(self.session.execute(stmt).scalars().all())
        for p in projects:
            self.session.delete(p)
        self.session.flush()
        return len(projects)