"""
Phase 8 integration: parse → build_query → run against a seeded DB.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Job
from app.services.search import build_query, parse_query


@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_search_"))
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
def seeded_jobs(session):
    now = datetime.now(timezone.utc)
    jobs = [
        Job(
            title="Junior Python Developer",
            company="Acme",
            location="Johannesburg",
            country="South Africa",
            seniority="junior",
            employment_type="permanent",
            remote_status="hybrid",
            description="Python, FastAPI, SQL.",
            source="manual",
            status="discovered",
            date_found=now,
            availability_status="open",
        ),
        Job(
            title="Senior Backend Developer",
            company="Beta",
            location="Cape Town",
            country="South Africa",
            seniority="senior",
            employment_type="permanent",
            remote_status="onsite",
            description="Java, Spring Boot.",
            source="manual",
            status="discovered",
            date_found=now - timedelta(days=2),
            availability_status="open",
        ),
        Job(
            title="Python Engineer",
            company="Gamma",
            location="Berlin",
            country="Germany",
            seniority="mid",
            employment_type="contract",
            remote_status="remote",
            description="Python, Django.",
            source="manual",
            status="discovered",
            date_found=now - timedelta(days=10),
            availability_status="open",
        ),
        Job(
            title="Data Scientist",
            company="Delta",
            location="Remote",
            country="United States",
            seniority="senior",
            employment_type="permanent",
            remote_status="remote",
            description="Python, pandas.",
            source="manual",
            status="discovered",
            date_found=now,
            availability_status="open",
        ),
    ]
    session.add_all(jobs)
    session.commit()
    return jobs


# ---------------------------------------------------------------- integration

def test_search_junior_python_johannesburg(session, seeded_jobs):
    filters = parse_query("junior python developer johannesburg")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    titles = {j.title for j in jobs}
    assert "Junior Python Developer" in titles


def test_search_remote(session, seeded_jobs):
    """
    'remote developer' should match software-role jobs whose remote_status
    is 'remote'. Data Scientist is not a developer role, so it should NOT
    match.
    """
    filters = parse_query("remote developer")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    remote_jobs = [j for j in jobs if j.remote_status == "remote"]
    assert len(remote_jobs) >= 1
    titles = {j.title for j in remote_jobs}
    assert "Python Engineer" in titles
    assert "Data Scientist" not in titles


def test_search_by_country(session, seeded_jobs):
    """'developer in Germany' should find the Python Engineer role."""
    filters = parse_query("developer in Germany")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    assert len(jobs) >= 1
    assert all(j.country == "Germany" for j in jobs)


def test_search_recent_only(session, seeded_jobs):
    filters = parse_query("developer last 3 days")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    for j in jobs:
        if j.date_posted:
            age_days = (datetime.now(timezone.utc) - j.date_posted).days
            assert age_days <= 3


def test_search_seniority(session, seeded_jobs):
    """
    'senior developer' should match senior software-role jobs.
    The Data Scientist is senior but not a developer role.
    """
    filters = parse_query("senior developer")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    assert all(j.seniority == "senior" for j in jobs)
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Backend Developer"


def test_search_developer_matches_engineer_titles(session, seeded_jobs):
    """
    'developer' is a broad role word — it should match jobs titled
    'Engineer' as well, because they're developer roles.
    """
    filters = parse_query("developer")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    titles = {j.title for j in jobs}
    assert "Python Engineer" in titles
    assert "Junior Python Developer" in titles
    assert "Senior Backend Developer" in titles
    assert "Data Scientist" not in titles


def test_search_python_developer_requires_both_words(session, seeded_jobs):
    """
    A specific family like 'Python Developer' requires BOTH words in the
    job title or description.
    """
    filters = parse_query("python developer")
    jobs = list(session.execute(build_query(filters, limit=100)).scalars().all())
    titles = {j.title for j in jobs}
    assert "Junior Python Developer" in titles
    assert "Python Engineer" not in titles