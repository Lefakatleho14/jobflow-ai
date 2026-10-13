"""
Job import service.

Takes a raw job payload, normalizes it, checks for duplicates, and
either returns the existing Job or inserts a new one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.models import Job
from app.services.jobs.dedupe import find_existing
from app.services.jobs.hashing import content_hash
from app.services.jobs.normalizer import normalize_job_fields

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Outcome of a job import operation."""
    job: Job
    created: bool   # True if a new row was inserted, False if duplicate found
    reason: str     # "created" | "duplicate"


class JobImportService:
    """
    Stateless service. Instantiate with a Session and call `.import_job(payload)`.

    The caller commits (or uses `session_scope()` which commits automatically).
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

        existing = find_existing(
            self.session,
            source=normalized["source"],
            external_id=normalized["external_id"],
            url=normalized["url"],
            content_hash_value=hash_value,
        )

        if existing is not None:
            logger.info("Duplicate job detected: id=%s", existing.id)
            return ImportResult(job=existing, created=False, reason="duplicate")

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
        self.session.flush()  # assigns UUID, validates constraints
        logger.info("Imported new job: id=%s title=%r", job.id, job.title)
        return ImportResult(job=job, created=True, reason="created")