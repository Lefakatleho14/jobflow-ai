"""
ProfileService — CRUD for the single local user's Profile.

Local-first design: exactly one user and one profile.
`ensure_default_user()` is idempotent — safe to call on every startup.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Profile, User
from app.services.profile.errors import ProfileError

logger = logging.getLogger(__name__)

# JSON-list fields stored on Profile.
_LIST_FIELDS = {
    "languages",
    "frameworks",
    "databases",
    "cloud",
    "devops",
    "tools",
    "certifications",
    "preferred_titles",
    "preferred_locations",
}

# Scalar fields that can be updated via update_scalar.
_SCALAR_FIELDS = {
    "name",
    "education",
    "degree",
    "experience_summary",
}

VALID_REMOTE_PREFERENCES = {"any", "remote", "hybrid", "onsite"}


def ensure_default_user(session: Session) -> User:
    """
    Return the local user, creating one if it doesn't exist.
    Idempotent — safe to call on every startup.
    """
    stmt = select(User).order_by(User.created_at).limit(1)
    user = session.execute(stmt).scalar_one_or_none()
    if user is None:
        user = User(display_name="Me")
        session.add(user)
        session.flush()
        logger.info("Created default user: id=%s", user.id)
    return user


class ProfileService:
    """CRUD for the single local profile."""

    def __init__(self, session: Session):
        self.session = session

    # ---- Read ----

    def get_profile(self) -> Profile | None:
        stmt = select(Profile).order_by(Profile.created_at).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()

    def ensure_profile(self) -> Profile:
        """Return the profile, creating a blank one if needed."""
        existing = self.get_profile()
        if existing is not None:
            return existing

        user = ensure_default_user(self.session)
        profile = Profile(user_id=user.id)
        self.session.add(profile)
        self.session.flush()
        logger.info("Created new profile: id=%s", profile.id)
        return profile

    # ---- Scalar updates ----

    def update_scalar(self, field: str, value: Any) -> Profile:
        if field not in _SCALAR_FIELDS:
            raise ProfileError(
                f"'{field}' is not a scalar field. Valid: {sorted(_SCALAR_FIELDS)}"
            )
        profile = self.ensure_profile()
        cleaned = str(value).strip() if value is not None else None
        setattr(profile, field, cleaned or None)
        self.session.flush()
        return profile

    # ---- List updates ----

    def update_list(self, field: str, values: list[str]) -> Profile:
        if field not in _LIST_FIELDS:
            raise ProfileError(
                f"'{field}' is not a list field. Valid: {sorted(_LIST_FIELDS)}"
            )
        if not isinstance(values, list):
            raise ProfileError(f"'{field}' must be a list of strings")

        cleaned = [str(v).strip() for v in values if str(v).strip()]
        # Deduplicate while preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for v in cleaned:
            key = v.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(v)

        profile = self.ensure_profile()
        setattr(profile, field, deduped)
        self.session.flush()
        return profile

    def add_to_list(self, field: str, value: str) -> Profile:
        profile = self.ensure_profile()
        current = getattr(profile, field, None)
        if current is None:
            raise ProfileError(f"Unknown field: {field}")
        if not str(value).strip():
            raise ProfileError("Value cannot be empty")
        new_list = list(current) + [str(value).strip()]
        return self.update_list(field, new_list)

    # ---- Preferences ----

    def update_preferences(
        self,
        *,
        remote_preference: str | None = None,
        minimum_match_score: int | None = None,
    ) -> Profile:
        profile = self.ensure_profile()

        if remote_preference is not None:
            rp = str(remote_preference).strip().lower()
            if rp not in VALID_REMOTE_PREFERENCES:
                raise ProfileError(
                    f"remote_preference must be one of "
                    f"{sorted(VALID_REMOTE_PREFERENCES)}, got {rp!r}"
                )
            profile.remote_preference = rp

        if minimum_match_score is not None:
            try:
                score = int(minimum_match_score)
            except (TypeError, ValueError):
                raise ProfileError("minimum_match_score must be an integer")
            if not 0 <= score <= 100:
                raise ProfileError("minimum_match_score must be between 0 and 100")
            profile.minimum_match_score = score

        self.session.flush()
        return profile

    # ---- Serialization ----

    def to_dict(self) -> dict:
        profile = self.get_profile()
        if profile is None:
            return {
                "exists": False,
                "name": None,
                "education": None,
                "degree": None,
                "languages": [],
                "frameworks": [],
                "databases": [],
                "cloud": [],
                "devops": [],
                "tools": [],
                "certifications": [],
                "preferred_titles": [],
                "preferred_locations": [],
                "remote_preference": "any",
                "minimum_match_score": 70,
                "experience_summary": None,
                "skills_count": 0,
                "projects_count": 0,
            }

        return {
            "exists": True,
            "id": profile.id,
            "user_id": profile.user_id,
            "name": profile.name,
            "education": profile.education,
            "degree": profile.degree,
            "languages": profile.languages,
            "frameworks": profile.frameworks,
            "databases": profile.databases,
            "cloud": profile.cloud,
            "devops": profile.devops,
            "tools": profile.tools,
            "certifications": profile.certifications,
            "preferred_titles": profile.preferred_titles,
            "preferred_locations": profile.preferred_locations,
            "remote_preference": profile.remote_preference,
            "minimum_match_score": profile.minimum_match_score,
            "experience_summary": profile.experience_summary,
            "skills_count": len(profile.skills),
            "projects_count": len(profile.projects),
        }

    # ---- Destructive ----

    def reset(self, *, confirm: bool = False) -> None:
        """Delete the current profile (and cascading skills/projects). Requires confirm=True."""
        if not confirm:
            raise ProfileError("reset requires confirm=True")
        profile = self.get_profile()
        if profile is None:
            return
        self.session.delete(profile)
        self.session.flush()
        logger.warning("Profile reset: id=%s", profile.id)