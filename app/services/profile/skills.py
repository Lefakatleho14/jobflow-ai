"""
SkillService — CRUD for skills on the local profile.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Skill
from app.models.enums import Proficiency, SkillCategory
from app.services.profile.errors import ProfileError
from app.services.profile.service import ProfileService

logger = logging.getLogger(__name__)


def _validate_category(category: str) -> str:
    value = str(category).strip().lower()
    valid = {c.value for c in SkillCategory}
    if value not in valid:
        raise ProfileError(
            f"Invalid skill category {value!r}. Valid: {sorted(valid)}"
        )
    return value


def _validate_proficiency(proficiency: str) -> str:
    value = str(proficiency).strip().lower()
    valid = {p.value for p in Proficiency}
    if value not in valid:
        raise ProfileError(
            f"Invalid proficiency {value!r}. Valid: {sorted(valid)}"
        )
    return value


class SkillService:
    def __init__(self, session: Session):
        self.session = session

    def list_skills(self) -> list[Skill]:
        profile = ProfileService(self.session).ensure_profile()
        stmt = select(Skill).where(Skill.profile_id == profile.id).order_by(Skill.name)
        return list(self.session.execute(stmt).scalars().all())

    def get_skill(self, name: str) -> Skill | None:
        profile = ProfileService(self.session).ensure_profile()
        stmt = select(Skill).where(
            Skill.profile_id == profile.id,
            Skill.name == name.strip(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def add_skill(
        self,
        name: str,
        *,
        category: str = "other",
        proficiency: str = "intermediate",
        years: float | None = None,
        evidence: str | None = None,
    ) -> Skill:
        """
        Add a skill. If a skill with the same name already exists on the
        profile, update it (idempotent).
        """
        cleaned_name = str(name).strip()
        if not cleaned_name:
            raise ProfileError("skill name cannot be empty")

        cat = _validate_category(category)
        prof = _validate_proficiency(proficiency)

        if years is not None:
            try:
                years = float(years)
            except (TypeError, ValueError):
                raise ProfileError("years must be a number")
            if years < 0:
                raise ProfileError("years cannot be negative")

        profile = ProfileService(self.session).ensure_profile()

        stmt = select(Skill).where(
            Skill.profile_id == profile.id,
            Skill.name == cleaned_name,
        )
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing is not None:
            existing.category = cat
            existing.proficiency = prof
            existing.years = years
            existing.evidence = evidence
            self.session.flush()
            logger.info("Updated skill: %s", cleaned_name)
            return existing

        skill = Skill(
            profile_id=profile.id,
            name=cleaned_name,
            category=cat,
            proficiency=prof,
            years=years,
            evidence=evidence,
        )
        self.session.add(skill)
        self.session.flush()
        logger.info("Added skill: %s", cleaned_name)
        return skill

    def remove_skill(self, name: str) -> bool:
        skill = self.get_skill(name)
        if skill is None:
            return False
        self.session.delete(skill)
        self.session.flush()
        return True

    def clear(self) -> int:
        profile = ProfileService(self.session).ensure_profile()
        stmt = select(Skill).where(Skill.profile_id == profile.id)
        skills = list(self.session.execute(stmt).scalars().all())
        for s in skills:
            self.session.delete(s)
        self.session.flush()
        return len(skills)