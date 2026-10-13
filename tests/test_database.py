"""
Phase 2 tests: schema creation, CRUD, relationships.

These tests use a temporary SQLite file per test to stay isolated.
They do NOT touch data/app.db.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import (
    Application,
    AutomationRun,
    Job,
    JobMatch,
    JobRequirement,
    Notification,
    Profile,
    Project,
    Skill,
    User,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture()
def session_factory():
    """Create a fresh SQLite file in a temp dir for each test."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_test_"))
    db_file = tmp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield Session
    engine.dispose()


@pytest.fixture()
def session(session_factory):
    """
    Yield a Session and ensure clean teardown.

    We do NOT auto-commit here. Every test commits explicitly when it
    wants to persist. This avoids the trap where a test deliberately
    triggers an IntegrityError (via pytest.raises), catches it, and yet
    leaves the session in a 'pending rollback' state that would blow up
    an unconditional `session.commit()` in teardown.
    """
    s = session_factory()
    try:
        yield s
    finally:
        if not s.is_active:
            s.rollback()
        s.close()


# ---------------------------------------------------------------- schema

def test_all_tables_created(session_factory):
    engine = session_factory.kw["bind"]
    tables = set(inspect(engine).get_table_names())
    expected = {
        "users", "profiles", "skills", "projects",
        "jobs", "job_requirements", "job_matches",
        "applications", "notifications", "automation_runs",
    }
    assert expected.issubset(tables), f"Missing: {expected - tables}"


# ---------------------------------------------------------------- user / profile

def test_create_user_and_profile(session):
    user = User(display_name="Katleho", email="k@example.com")
    profile = Profile(name="Katleho M.", education="BSc Computer Science")
    user.profile = profile
    session.add(user)
    session.commit()

    fetched = session.query(User).filter_by(email="k@example.com").one()
    assert fetched.display_name == "Katleho"
    assert fetched.profile is not None
    assert fetched.profile.education == "BSc Computer Science"


def test_profile_json_roundtrip(session):
    user = User(display_name="Tester")
    profile = Profile()
    profile.languages = ["Python", "Java"]
    profile.frameworks = ["FastAPI", "Spring Boot"]
    user.profile = profile
    session.add(user)
    session.commit()

    loaded = session.query(Profile).one()
    assert loaded.languages == ["Python", "Java"]
    assert loaded.frameworks == ["FastAPI", "Spring Boot"]


def test_skills_and_projects_relationship(session):
    user = User(display_name="Tester")
    profile = Profile()
    profile.skills = [
        Skill(name="Python", category="language", proficiency="advanced"),
        Skill(name="FastAPI", category="framework", proficiency="intermediate"),
    ]
    p = Project(name="JobFlow AI", description="Portfolio project")
    p.technologies = ["Python", "FastAPI", "SQLite"]
    profile.projects = [p]
    user.profile = profile
    session.add(user)
    session.commit()

    loaded = session.query(Profile).one()
    assert {s.name for s in loaded.skills} == {"Python", "FastAPI"}
    assert loaded.projects[0].technologies == ["Python", "FastAPI", "SQLite"]


# ---------------------------------------------------------------- jobs

def test_create_job_with_requirement_and_match(session):
    user = User(display_name="Tester")
    user.profile = Profile()
    session.add(user)
    session.commit()
    profile_id = user.profile.id

    job = Job(
        title="Junior Software Developer",
        company="Acme",
        location="Johannesburg",
        description="Python, FastAPI, SQLite",
        source="manual",
        remote_status="hybrid",
        status="matched",
        content_hash="abc123",
    )
    req = JobRequirement(job=job, seniority="junior", experience_years=1)
    req.languages = ["Python"]
    req.frameworks = ["FastAPI"]

    match = JobMatch(
        job=job,
        profile_id=profile_id,
        score=92.0,
        tier="high",
        technical_score=40,
        education_score=18,
        experience_score=14,
        projects_score=10,
        location_score=8,
        other_score=2,
        explanation="Strong match on Python and FastAPI.",
    )
    match.strong_matches = ["Python", "FastAPI"]
    match.missing_skills = ["Docker"]

    session.add_all([job, req, match])
    session.commit()

    loaded = session.query(Job).filter_by(company="Acme").one()
    assert loaded.requirement.languages == ["Python"]
    assert loaded.match.tier == "high"
    assert loaded.match.missing_skills == ["Docker"]


def test_application_relationship(session):
    user = User(display_name="Tester")
    user.profile = Profile()
    session.add(user)
    session.commit()

    job = Job(title="Backend Dev", company="Beta", status="approved")
    app = Application(job=job, status="applied", notes="Submitted via portal")
    session.add_all([job, app])
    session.commit()

    loaded = session.query(Job).filter_by(company="Beta").one()
    assert loaded.application.status == "applied"
    assert loaded.application.notes == "Submitted via portal"


def test_automation_run_defaults(session):
    run = AutomationRun(status="success")
    session.add(run)
    session.commit()
    assert run.jobs_added == 0
    assert run.errors == 0


def test_notification_optional_links(session):
    note = Notification(type="system", title="DB ready")
    session.add(note)
    session.commit()
    assert note.is_read is False
    assert note.job_id is None


# ---------------------------------------------------------------- uniqueness

def test_skill_unique_per_profile(session):
    user = User(display_name="Tester")
    profile = Profile()
    profile.skills = [Skill(name="Python"), Skill(name="Python")]
    user.profile = profile
    session.add(user)
    with pytest.raises(Exception):
        session.commit()