"""
Fuzzy alias lookup.

Given a rejected payload, find the most similar recent job from the
same company and, if the score crosses the threshold, create a JobAlias.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobAlias
from app.services.jobs.fuzzy import combined_similarity, companies_match

logger = logging.getLogger(__name__)


@dataclass
class AliasDecision:
    """Outcome of a fuzzy lookup."""
    job: Optional[Job]           # the matched job, if any
    similarity: float            # combined score
    title_similarity: float
    location_similarity: float
    reason: str                  # human-readable explanation
    created_alias: bool          # True if a JobAlias row was created


def _candidate_jobs(
    session: Session,
    *,
    company: str,
    window_days: int,
    limit: int = 200,
) -> list[Job]:
    """
    Return candidate jobs from the same (normalized) company within a
    recent time window. Company matching is fuzzy at the token level.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = (
        select(Job)
        .where(Job.date_found >= cutoff)
        .order_by(Job.date_found.desc())
        .limit(limit)
    )
    jobs = list(session.execute(stmt).scalars().all())
    return [j for j in jobs if companies_match(j.company, company)]


def find_fuzzy_match(
    session: Session,
    *,
    company: str,
    title: str,
    location: Optional[str],
    window_days: int = 90,
    threshold: float = 0.87,
) -> Optional[tuple[Job, float, float, float]]:
    """
    Return (job, combined, title_sim, location_sim) for the best match
    at or above `threshold`, or None.
    """
    candidates = _candidate_jobs(session, company=company, window_days=window_days)
    if not candidates:
        return None

    best: Optional[tuple[Job, float, float, float]] = None
    for job in candidates:
        combined, t, l = combined_similarity(
            title_a=title,
            title_b=job.title,
            location_a=location,
            location_b=job.location,
        )
        if combined >= threshold:
            if best is None or combined > best[1]:
                best = (job, combined, t, l)

    return best


def record_alias(
    session: Session,
    *,
    job: Job,
    payload: dict,
    content_hash_value: str,
    similarity: float,
    title_similarity: float,
    location_similarity: float,
) -> JobAlias:
    """Create a JobAlias row linking the payload to the matched job."""
    reason = (
        f"Fuzzy match: title={title_similarity:.2f}, "
        f"location={location_similarity:.2f}, combined={similarity:.2f}"
    )
    alias = JobAlias(
        job_id=job.id,
        alias_hash=content_hash_value,
        alias_title=payload.get("title") or "",
        alias_company=payload.get("company") or "",
        alias_location=payload.get("location"),
        alias_source=payload.get("source"),
        alias_url=payload.get("url"),
        similarity=similarity,
        title_similarity=title_similarity,
        location_similarity=location_similarity,
        reason=reason,
    )
    session.add(alias)
    session.flush()
    logger.info("Created JobAlias: job=%s sim=%.2f", job.id, similarity)
    return alias


def alias_exists(
    session: Session,
    *,
    job_id: str,
    content_hash_value: str,
) -> bool:
    """Check whether this (job_id, alias_hash) pair already exists."""
    stmt = select(JobAlias).where(
        JobAlias.job_id == job_id,
        JobAlias.alias_hash == content_hash_value,
    )
    return session.execute(stmt).scalar_one_or_none() is not None