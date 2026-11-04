"""
JobFilters → SQLAlchemy Select against the `jobs` table.

Kept separate from the parser so we can test SQL construction independently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.sql import Select

from app.models import Job
from app.services.search.filters import JobFilters


def build_query(filters: JobFilters, *, limit: int = 100) -> Select:
    """
    Build a SELECT over `jobs` for the given filters. Never returns None.
    """
    stmt = select(Job)

    # Filter out jobs that are clearly unavailable.
    stmt = stmt.where(
        or_(
            Job.availability_status.is_(None),
            Job.availability_status.in_(["open", "unverified", "closing_soon"]),
        )
    )

    if filters.titles:
        broad_role_words = {
            "developer", "engineer", "programmer", "software",
            "dev", "swe", "sde",
        }

        specific_families = [t for t in filters.titles if t != "Software Developer"]
        only_broad = not specific_families

        family_conditions = []
        for canonical in filters.titles:
            if canonical == "Software Developer":
                if only_broad:
                    # Broad family only: any broad role word matches.
                    for word in broad_role_words:
                        family_conditions.append(Job.title.ilike(f"%{word}%"))
                # else: skip — specific family already implies broad.
                continue

            # Specific family: title must contain ALL significant words (AND).
            words = [w for w in canonical.lower().split() if len(w) > 2]
            if words:
                per_word = [Job.title.ilike(f"%{word}%") for word in words]
                family_conditions.append(and_(*per_word))

        if family_conditions:
            # Combine families with OR (a job matching any family is a hit).
            stmt = stmt.where(or_(*family_conditions))

    if filters.seniority:
        stmt = stmt.where(Job.seniority.in_(filters.seniority))

    if filters.employment_types:
        stmt = stmt.where(Job.employment_type.in_(filters.employment_types))

    if filters.remote_preference:
        stmt = stmt.where(Job.remote_status == filters.remote_preference)

    if filters.countries:
        stmt = stmt.where(Job.country.in_(filters.countries))

    if filters.locations:
        loc_conditions = [Job.location.ilike(f"%{city}%") for city in filters.locations]
        stmt = stmt.where(or_(*loc_conditions))

    if filters.required_skills:
        for skill in filters.required_skills:
            stmt = stmt.where(
                or_(
                    Job.description.ilike(f"%{skill}%"),
                    Job.title.ilike(f"%{skill}%"),
                )
            )

    if filters.date_posted_within_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=filters.date_posted_within_days)
        stmt = stmt.where(
            or_(
                Job.date_posted.is_(None),
                Job.date_posted >= cutoff,
            )
        )

    # Stable ordering: freshest first, then by insertion time.
    stmt = stmt.order_by(Job.date_found.desc().nullslast(), Job.id.desc())
    stmt = stmt.limit(limit)
    return stmt