"""
Job import service.

Order of operations:
    1. normalize
    2. compute content hash
    3. deterministic dedupe (source+external_id, url, content_hash)
    4. fuzzy dedupe (same company, similar title/location) → creates alias
    5. insert

Only step 5 creates a Job. Step 4 creates a JobAlias row for later review.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.models import Job
from app.services.jobs.alias import (
    alias_exists,
    find_fuzzy_match,
    record_alias,
)
from app.services.jobs.dedupe import find_existing
from app.services.jobs.hashing import content_hash
from app.services.jobs.normalizer import normalize_job_fields

logger = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class ImportResult:
    """Outcome of a job import operation."""
    job: Job
    created: bool
    reason: str                    # "created" | "duplicate" | "fuzzy_alias"
    alias_similarity: float = 0.0


class JobImportService:
    """
    Stateless service. Instantiate with a Session and call `.import_job(payload)`.
    Caller commits (or uses `session_scope()`).
    """

    def __init__(self, session: Session):
        self.session = session

    def import_job(self, payload: dict[str, Any]) -> ImportResult:
        normalized = normalize_job_fields(payload)
        hash_value = content_hash(
            company=normalized["company"],
            title=normalized["title"],
            location=normalized["location"],
        )

        # --- Layer 1: deterministic ---
        existing = find_existing(
            self.session,
            source=normalized["source"],
            external_id=normalized["external_id"],
            url=normalized["url"],
            content_hash_value=hash_value,
        )
        if existing is not None:
            logger.info("Deterministic duplicate: id=%s", existing.id)
            return ImportResult(job=existing, created=False, reason="duplicate")

        # --- Layer 2: fuzzy ---
        threshold = _env_float("FUZZY_MATCH_THRESHOLD", 0.82)
        window_days = _env_int("FUZZY_COMPANY_WINDOW_DAYS", 90)

        fuzzy = find_fuzzy_match(
            self.session,
            company=normalized["company"],
            title=normalized["title"],
            location=normalized["location"],
            window_days=window_days,
            threshold=threshold,
        )
        if fuzzy is not None:
            job, combined, t, l = fuzzy

            # Idempotency: don't re-create the same alias twice
            if not alias_exists(self.session, job_id=job.id, content_hash_value=hash_value):
                record_alias(
                    self.session,
                    job=job,
                    payload=normalized,
                    content_hash_value=hash_value,
                    similarity=combined,
                    title_similarity=t,
                    location_similarity=l,
                )

            logger.info(
                "Fuzzy alias: id=%s sim=%.2f (t=%.2f, l=%.2f)",
                job.id, combined, t, l,
            )
            return ImportResult(
                job=job,
                created=False,
                reason="fuzzy_alias",
                alias_similarity=combined,
            )

        # --- Layer 3: insert ---
        job = Job(
            title=normalized["title"],
            company=normalized["company"],
            location=normalized["location"],
            remote_status=normalized["remote_status"],
            description=normalized["description"],
            url=normalized["url"],
            source=normalized["source"],
            external_id=normalized["external_id"],
            date_posted=normalized["date_posted"],
            date_found=utc_now(),
            status="discovered",
            salary_min=normalized["salary_min"],
            salary_max=normalized["salary_max"],
            salary_currency=normalized["salary_currency"],
            content_hash=hash_value,
        )
        self.session.add(job)
        self.session.flush()
        logger.info("Imported new job: id=%s title=%r", job.id, job.title)
        return ImportResult(job=job, created=True, reason="created")