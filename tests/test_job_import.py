"""
Phase 3 tests: normalization, hashing, dedupe, end-to-end import.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Job
from app.services.jobs import (
    JobImportService,
    content_hash,
    normalize_job_fields,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_import_"))
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


@pytest.fixture()
def minimal_payload() -> dict:
    return {
        "title": "Junior Software Developer",
        "company": "Acme",
        "location": "Johannesburg",
        "description": "Python role.",
        "source": "manual",
    }


# ---------------------------------------------------------------- normalizer

def test_title_whitespace_collapsed():
    result = normalize_job_fields({
        "title": "  Junior   Software   Developer  ",
        "company": "Acme",
    })
    assert result["title"] == "Junior Software Developer"


def test_company_trailing_punctuation_stripped():
    result = normalize_job_fields({
        "title": "Dev",
        "company": "Acme Holdings, Inc.",
    })
    assert result["company"] == "Acme Holdings, Inc"


def test_company_required():
    with pytest.raises(ValueError):
        normalize_job_fields({"title": "Dev", "company": "   "})


def test_title_required():
    with pytest.raises(ValueError):
        normalize_job_fields({"title": "  ", "company": "Acme"})


@pytest.mark.parametrize("raw,expected", [
    ("Work from Home", "remote"),
    ("WFH", "remote"),
    ("on-site", "onsite"),
    ("Hybrid", "hybrid"),
    ("", "unknown"),
    (None, "unknown"),
    ("nonsense", "unknown"),
])
def test_remote_status_mapping(raw, expected):
    result = normalize_job_fields({
        "title": "Dev", "company": "Acme", "remote_status": raw,
    })
    assert result["remote_status"] == expected


def test_description_normalization():
    raw = "Line1\r\n\r\n\r\n\r\nLine2\n\n\n\nLine3"
    result = normalize_job_fields({
        "title": "Dev", "company": "Acme", "description": raw,
    })
    assert "\r" not in result["description"]
    assert "\n\n\n" not in result["description"]
    assert result["description"].startswith("Line1")


def test_salary_validation_ok():
    result = normalize_job_fields({
        "title": "Dev", "company": "Acme",
        "salary_min": "100000", "salary_max": 200000, "salary_currency": "zar",
    })
    assert result["salary_min"] == 100000
    assert result["salary_max"] == 200000
    assert result["salary_currency"] == "ZAR"


def test_salary_min_greater_than_max_rejected():
    with pytest.raises(ValueError):
        normalize_job_fields({
            "title": "Dev", "company": "Acme",
            "salary_min": 300000, "salary_max": 100000,
        })


def test_salary_currency_must_be_three_letters():
    with pytest.raises(ValueError):
        normalize_job_fields({
            "title": "Dev", "company": "Acme", "salary_currency": "RAND",
        })


def test_normalization_is_idempotent():
    once = normalize_job_fields({
        "title": "  Dev  ", "company": "Acme,",
        "location": " Joburg  ", "description": "A\r\nB\r\n\r\n\r\nC",
    })
    twice = normalize_job_fields(once)
    assert once == twice


# ---------------------------------------------------------------- hashing

def test_hash_is_deterministic():
    h1 = content_hash("Acme", "Dev", "Johannesburg")
    h2 = content_hash("Acme", "Dev", "Johannesburg")
    assert h1 == h2
    assert len(h1) == 32


def test_hash_case_insensitive():
    assert content_hash("ACME", "DEV", "JOBURG") == content_hash("acme", "dev", "joburg")


def test_hash_distinguishes_different_jobs():
    assert content_hash("Acme", "Dev", "Joburg") != content_hash("Acme", "Dev", "Cape Town")


def test_hash_none_location_equivalent_to_empty():
    assert content_hash("Acme", "Dev", None) == content_hash("Acme", "Dev", "")


# ---------------------------------------------------------------- import

def test_import_creates_new_job(session, minimal_payload):
    result = JobImportService(session).import_job(minimal_payload)
    session.commit()
    assert result.created is True
    assert result.job.title == "Junior Software Developer"
    assert result.job.status == "discovered"
    assert result.job.content_hash is not None
    assert session.query(Job).count() == 1


def test_import_is_idempotent_by_content_hash(session, minimal_payload):
    service = JobImportService(session)
    first = service.import_job(minimal_payload)
    session.commit()

    second = service.import_job(minimal_payload)
    session.commit()

    assert first.created is True
    assert second.created is False
    assert first.job.id == second.job.id
    assert session.query(Job).count() == 1


def test_duplicate_detection_by_source_and_external_id(session, minimal_payload):
    payload = dict(minimal_payload)
    payload["external_id"] = "abc-123"
    payload["url"] = "https://example.com/a"

    service = JobImportService(session)
    service.import_job(payload)
    session.commit()

    payload2 = dict(payload)
    payload2["title"] = "Different Title"
    payload2["url"] = "https://example.com/b"

    second = service.import_job(payload2)
    session.commit()
    assert second.created is False


def test_duplicate_detection_by_url(session, minimal_payload):
    payload = dict(minimal_payload)
    payload["url"] = "https://example.com/same"

    service = JobImportService(session)
    service.import_job(payload)
    session.commit()

    payload2 = {
        "title": "Another Title",
        "company": "Another Co",
        "location": "Cape Town",
        "description": "Something",
        "source": "manual",
        "url": "https://example.com/same",
    }
    second = service.import_job(payload2)
    session.commit()
    assert second.created is False


def test_duplicate_detection_by_content_hash(session, minimal_payload):
    service = JobImportService(session)
    service.import_job(minimal_payload)
    session.commit()

    payload2 = dict(minimal_payload)
    payload2["source"] = "rss"
    payload2["description"] = "A completely different description."

    second = service.import_job(payload2)
    session.commit()
    assert second.created is False
    assert session.query(Job).count() == 1


def test_same_title_different_location_not_duplicate(session, minimal_payload):
    service = JobImportService(session)
    service.import_job(minimal_payload)
    session.commit()

    payload2 = dict(minimal_payload)
    payload2["location"] = "Cape Town"
    result2 = service.import_job(payload2)
    session.commit()

    assert result2.created is True
    assert session.query(Job).count() == 2