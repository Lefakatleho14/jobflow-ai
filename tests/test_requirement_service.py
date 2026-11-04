"""
Phase 10 tests: RequirementService orchestration with mocked LLM.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ai.errors import LLMResponseError, LLMUnavailableError
from app.database.base import Base
from app.models import Job, JobRequirement
from app.services.jobs import RequirementService


@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_req_"))
    db_file = tmp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                           expire_on_commit=False)
    yield Session
    engine.dispose()


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    try:
        yield s
    finally:
        if not s.is_active:
            s.rollback()
        s.close()


def _make_job(session, title="Dev", description="Python, FastAPI"):
    job = Job(
        title=title,
        company="Acme",
        description=description,
        source="manual",
        status="discovered",
        date_found=datetime.now(timezone.utc),
        availability_status="open",
    )
    session.add(job)
    session.commit()
    return job


def _mock_llm(success_dict=None, error=None):
    llm = MagicMock()
    if error:
        llm.extract_job_requirements.side_effect = error
    else:
        llm.extract_job_requirements.return_value = success_dict or {}
    return llm


# ---------------------------------------------------------------- happy path

def test_extract_one_creates_requirement(session):
    job = _make_job(session)
    llm = _mock_llm({
        "title": "Junior Dev",
        "seniority": "junior",
        "languages": ["Python"],
        "frameworks": ["FastAPI"],
    })
    svc = RequirementService(session, llm=llm)
    result = svc.extract_one(job)
    session.commit()

    assert result.status == "extracted"
    req = session.execute(select(JobRequirement)).scalar_one()
    assert req.seniority == "junior"
    assert req.languages == ["Python"]
    assert req.frameworks == ["FastAPI"]


def test_extract_one_skips_if_already_extracted(session):
    job = _make_job(session)
    llm = _mock_llm({"seniority": "junior"})
    svc = RequirementService(session, llm=llm)

    svc.extract_one(job)
    session.commit()

    result2 = svc.extract_one(job)
    assert result2.status == "skipped"
    assert "already" in result2.reason.lower()


def test_extract_one_skips_empty_description(session):
    job = _make_job(session, description="")
    llm = _mock_llm({"seniority": "junior"})
    svc = RequirementService(session, llm=llm)

    result = svc.extract_one(job)
    assert result.status == "skipped"
    assert "empty" in result.reason.lower()


# ---------------------------------------------------------------- LLM failure

def test_extract_one_handles_llm_error(session):
    job = _make_job(session)
    llm = _mock_llm(error=LLMResponseError("bad json"))
    svc = RequirementService(session, llm=llm)

    result = svc.extract_one(job)
    assert result.status == "failed"
    assert "LLM error" in result.reason
    assert session.execute(select(JobRequirement)).first() is None


def test_extract_one_handles_llm_unavailable(session):
    job = _make_job(session)
    llm = _mock_llm(error=LLMUnavailableError("down"))
    svc = RequirementService(session, llm=llm)

    result = svc.extract_one(job)
    assert result.status == "failed"
    assert "down" in result.reason


# ---------------------------------------------------------------- invalid output

def test_extract_one_rejects_non_dict(session):
    job = _make_job(session)
    llm = MagicMock()
    llm.extract_job_requirements.return_value = "not a dict"
    svc = RequirementService(session, llm=llm)

    result = svc.extract_one(job)
    assert result.status == "failed"
    assert "dict" in result.reason.lower()


# ---------------------------------------------------------------- batch

def test_extract_batch_processes_pending(session):
    j1 = _make_job(session, title="Dev 1")
    j2 = _make_job(session, title="Dev 2")
    llm = _mock_llm({"languages": ["Python"]})
    svc = RequirementService(session, llm=llm)

    report = svc.extract_batch(limit=10)
    assert report.total_candidates == 2
    assert report.extracted == 2
    assert report.failed == 0
    assert session.execute(select(JobRequirement)).all() != []


def test_extract_batch_respects_limit(session):
    for i in range(5):
        _make_job(session, title=f"Dev {i}")
    llm = _mock_llm({"languages": ["Python"]})
    svc = RequirementService(session, llm=llm)

    report = svc.extract_batch(limit=2)
    assert report.total_candidates == 2
    assert report.extracted == 2


def test_extract_batch_continues_after_failure(session):
    j1 = _make_job(session, title="Good")
    j2 = _make_job(session, title="Bad")

    llm = MagicMock()
    def _side_effect(description):
        # First call succeeds, second fails, third succeeds
        if not hasattr(_side_effect, "count"):
            _side_effect.count = 0
        _side_effect.count += 1
        if _side_effect.count == 2:
            raise LLMResponseError("transient")
        return {"languages": ["Python"]}
    llm.extract_job_requirements.side_effect = _side_effect

    svc = RequirementService(session, llm=llm)
    report = svc.extract_batch(limit=10)
    assert report.total_candidates == 2
    assert report.extracted == 1
    assert report.failed == 1


def test_extract_batch_with_explicit_ids(session):
    j1 = _make_job(session, title="Dev 1")
    j2 = _make_job(session, title="Dev 2")
    llm = _mock_llm({"languages": ["Python"]})
    svc = RequirementService(session, llm=llm)

    report = svc.extract_batch(job_ids=[j1.id])
    assert report.total_candidates == 1
    assert report.extracted == 1
    assert session.execute(select(JobRequirement)).scalar_one().job_id == j1.id