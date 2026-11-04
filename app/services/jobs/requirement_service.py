"""
RequirementService — orchestrate extraction from a Job row.

For each job:
    1. Skip if already extracted (idempotent).
    2. Call LLMService.extract_job_requirements(job.description).
    3. Validate the raw output via JobRequirementSchema.
    4. If valid, insert/update a JobRequirement row.
    5. If invalid, log and skip — never save malformed data.

Batches are small (MAX_JOBS_PER_RUN) to fit 8 GB RAM constraint.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.errors import LLMError
from app.ai.llm_service import LLMService
from app.models import Job, JobRequirement
from app.services.jobs.requirement_schema import (
    JobRequirementSchema,
    parse_and_validate,
)

logger = logging.getLogger(__name__)


def _max_jobs_per_run() -> int:
    raw = os.getenv("MAX_JOBS_PER_RUN", "10")
    try:
        return int(raw)
    except ValueError:
        return 10


@dataclass
class ExtractionResult:
    """Outcome of a single job's extraction."""
    job_id: str
    job_title: str
    status: str                    # "extracted" | "skipped" | "failed"
    reason: str = ""
    duration_ms: int = 0


@dataclass
class BatchReport:
    """Aggregated outcome of a batch run."""
    total_candidates: int = 0
    extracted: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[ExtractionResult] = None

    def __post_init__(self) -> None:
        if self.results is None:
            self.results = []


class RequirementService:
    """
    Stateless. Instantiate with a Session, call extract_batch().
    """

    def __init__(self, session: Session, llm: LLMService | None = None):
        self.session = session
        self.llm = llm or LLMService()

    # ---- Single job ----

    def extract_one(self, job: Job) -> ExtractionResult:
        """
        Extract requirements for a single job.

        Does NOT commit — the caller commits after a successful insert.
        """
        # Check for an existing requirement by querying the DB directly.
        # This avoids relying on the `job.requirement` relationship, which
        # might be expired or lazy-loaded depending on session state.
        existing = self.session.execute(
            select(JobRequirement).where(JobRequirement.job_id == job.id)
        ).scalar_one_or_none()
        if existing is not None:
            return ExtractionResult(
                job_id=job.id,
                job_title=job.title,
                status="skipped",
                reason="already extracted",
            )

        if not job.description or not job.description.strip():
            return ExtractionResult(
                job_id=job.id,
                job_title=job.title,
                status="skipped",
                reason="empty description",
            )

        # Call the LLM.
        try:
            raw = self.llm.extract_job_requirements(job.description)
        except LLMError as exc:
            logger.warning("LLM failed on job %s: %s", job.id, exc)
            return ExtractionResult(
                job_id=job.id,
                job_title=job.title,
                status="failed",
                reason=f"LLM error: {exc}",
            )

        # Validate.
        schema, problems = parse_and_validate(raw)
        if schema is None:
            logger.warning("Invalid LLM output for job %s: %s", job.id, problems)
            return ExtractionResult(
                job_id=job.id,
                job_title=job.title,
                status="failed",
                reason="; ".join(problems),
            )

        # Persist.
        try:
            self._insert_requirement(job, schema, raw)
        except Exception as exc:
            logger.exception("DB insert failed for job %s", job.id)
            return ExtractionResult(
                job_id=job.id,
                job_title=job.title,
                status="failed",
                reason=f"DB error: {exc}",
            )

        return ExtractionResult(
            job_id=job.id,
            job_title=job.title,
            status="extracted",
            reason="ok",
        )

    def _insert_requirement(
        self,
        job: Job,
        schema: JobRequirementSchema,
        raw: dict,
    ) -> JobRequirement:
        """Create the JobRequirement row. Uses properties for JSON fields."""
        import json

        req = JobRequirement(
            job_id=job.id,
            seniority=schema.seniority,
            experience_years=schema.experience_years,
            salary=schema.salary,
            raw_json=json.dumps(raw, ensure_ascii=False)[:8000],
            extracted_at=datetime.now(timezone.utc),
        )
        req.languages = schema.languages
        req.frameworks = schema.frameworks
        req.databases = schema.databases
        req.cloud = schema.cloud
        req.devops = schema.devops
        req.soft_skills = schema.soft_skills
        req.education = schema.education
        self.session.add(req)
        self.session.flush()
        return req

    # ---- Batch ----

    def extract_batch(
        self,
        *,
        limit: Optional[int] = None,
        job_ids: Optional[list[str]] = None,
    ) -> BatchReport:
        """
        Extract requirements for a batch of jobs.

        Selection order:
            * If `job_ids` is given, process exactly those.
            * Otherwise, process up to `limit` (default MAX_JOBS_PER_RUN)
              jobs that don't yet have requirements, oldest-first.
        """
        report = BatchReport()

        if job_ids:
            jobs: list[Job] = list(
                self.session.execute(
                    select(Job).where(Job.id.in_(job_ids))
                ).scalars().all()
            )
        else:
            cap = limit if limit is not None else _max_jobs_per_run()
            # Left join: only jobs with no requirement row.
            stmt = (
                select(Job)
                .outerjoin(JobRequirement, JobRequirement.job_id == Job.id)
                .where(JobRequirement.id.is_(None))
                .order_by(Job.date_found.asc().nullsfirst(), Job.id.asc())
                .limit(cap)
            )
            jobs = list(self.session.execute(stmt).scalars().all())

        report.total_candidates = len(jobs)

        for job in jobs:
            try:
                result = self.extract_one(job)
            except Exception as exc:
                logger.exception("Unexpected error processing job %s", job.id)
                result = ExtractionResult(
                    job_id=job.id,
                    job_title=job.title,
                    status="failed",
                    reason=f"unexpected: {exc}",
                )

            report.results.append(result)
            if result.status == "extracted":
                report.extracted += 1
                self.session.commit()
            elif result.status == "skipped":
                report.skipped += 1
            else:
                report.failed += 1

        return report