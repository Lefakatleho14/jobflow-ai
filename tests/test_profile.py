"""
Phase 6 tests: ProfileService, SkillService, ProjectService CRUD and validation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Profile, Project, Skill, User
from app.services.profile import (
    ProfileError,
    ProfileService,
    ProjectService,
    SkillService,
    ensure_default_user,
)


@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_profile_"))
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


# ---------------------------------------------------------------- default user

def test_ensure_default_user_creates_once(session):
    u1 = ensure_default_user(session)
    session.commit()
    u2 = ensure_default_user(session)
    session.commit()
    assert u1.id == u2.id
    assert session.query(User).count() == 1


# ---------------------------------------------------------------- profile basics

def test_ensure_profile_creates(session):
    svc = ProfileService(session)
    p = svc.ensure_profile()
    session.commit()
    assert p.id is not None
    assert svc.get_profile().id == p.id


def test_ensure_profile_idempotent(session):
    svc = ProfileService(session)
    p1 = svc.ensure_profile()
    session.commit()
    p2 = svc.ensure_profile()
    session.commit()
    assert p1.id == p2.id
    assert session.query(Profile).count() == 1


def test_update_scalar(session):
    svc = ProfileService(session)
    svc.update_scalar("name", "Test Name")
    session.commit()
    assert svc.get_profile().name == "Test Name"


def test_update_scalar_invalid_field(session):
    svc = ProfileService(session)
    with pytest.raises(ProfileError):
        svc.update_scalar("nonexistent", "x")


def test_update_list_dedupes(session):
    svc = ProfileService(session)
    svc.update_list("languages", ["Python", "python", "Java", "PYTHON"])
    session.commit()
    assert svc.get_profile().languages == ["Python", "Java"]


def test_update_list_invalid_field(session):
    svc = ProfileService(session)
    with pytest.raises(ProfileError):
        svc.update_list("not_a_field", ["a"])


def test_add_to_list(session):
    svc = ProfileService(session)
    svc.update_list("frameworks", ["FastAPI"])
    svc.add_to_list("frameworks", "React")
    session.commit()
    assert set(svc.get_profile().frameworks) == {"FastAPI", "React"}


def test_update_preferences_valid(session):
    svc = ProfileService(session)
    svc.update_preferences(remote_preference="remote", minimum_match_score=85)
    session.commit()
    p = svc.get_profile()
    assert p.remote_preference == "remote"
    assert p.minimum_match_score == 85


def test_update_preferences_invalid_remote(session):
    svc = ProfileService(session)
    with pytest.raises(ProfileError):
        svc.update_preferences(remote_preference="sometimes")


def test_update_preferences_invalid_score(session):
    svc = ProfileService(session)
    with pytest.raises(ProfileError):
        svc.update_preferences(minimum_match_score=150)


def test_to_dict_empty(session):
    svc = ProfileService(session)
    d = svc.to_dict()
    assert d["exists"] is False
    assert d["languages"] == []


def test_to_dict_populated(session):
    svc = ProfileService(session)
    svc.update_scalar("name", "X")
    svc.update_list("languages", ["Python"])
    session.commit()
    d = svc.to_dict()
    assert d["exists"] is True
    assert d["name"] == "X"
    assert d["languages"] == ["Python"]


def test_reset_requires_confirm(session):
    svc = ProfileService(session)
    svc.ensure_profile()
    session.commit()
    with pytest.raises(ProfileError):
        svc.reset(confirm=False)


def test_reset_deletes_profile(session):
    svc = ProfileService(session)
    svc.ensure_profile()
    session.commit()
    svc.reset(confirm=True)
    session.commit()
    assert svc.get_profile() is None


# ---------------------------------------------------------------- skills

def test_add_skill(session):
    svc = SkillService(session)
    s = svc.add_skill("Python", category="language", proficiency="advanced", years=3)
    session.commit()
    assert s.id is not None
    assert s.name == "Python"
    assert session.query(Skill).count() == 1


def test_add_skill_idempotent(session):
    svc = SkillService(session)
    svc.add_skill("Python", category="language", proficiency="beginner")
    session.commit()
    svc.add_skill("Python", category="language", proficiency="advanced", years=2)
    session.commit()
    assert session.query(Skill).count() == 1
    s = session.query(Skill).one()
    assert s.proficiency == "advanced"
    assert s.years == 2


def test_add_skill_invalid_category(session):
    svc = SkillService(session)
    with pytest.raises(ProfileError):
        svc.add_skill("X", category="not-a-category")


def test_add_skill_invalid_proficiency(session):
    svc = SkillService(session)
    with pytest.raises(ProfileError):
        svc.add_skill("X", proficiency="guru")


def test_add_skill_negative_years(session):
    svc = SkillService(session)
    with pytest.raises(ProfileError):
        svc.add_skill("X", years=-1)


def test_add_skill_empty_name(session):
    svc = SkillService(session)
    with pytest.raises(ProfileError):
        svc.add_skill("  ")


def test_list_skills_ordered(session):
    svc = SkillService(session)
    svc.add_skill("Python")
    svc.add_skill("Docker")
    svc.add_skill("Git")
    session.commit()
    names = [s.name for s in svc.list_skills()]
    assert names == ["Docker", "Git", "Python"]


def test_remove_skill(session):
    svc = SkillService(session)
    svc.add_skill("Python")
    session.commit()
    assert svc.remove_skill("Python") is True
    session.commit()
    assert svc.remove_skill("Python") is False


def test_clear_skills(session):
    svc = SkillService(session)
    svc.add_skill("Python")
    svc.add_skill("Java")
    session.commit()
    assert svc.clear() == 2
    session.commit()
    assert svc.list_skills() == []


# ---------------------------------------------------------------- projects

def test_add_project(session):
    svc = ProjectService(session)
    p = svc.add_project(
        "JobFlow AI",
        description="Local-first job intelligence",
        technologies=["Python", "FastAPI"],
        role="Solo",
    )
    session.commit()
    assert p.id is not None
    assert p.name == "JobFlow AI"
    assert p.technologies == ["Python", "FastAPI"]


def test_add_project_idempotent(session):
    svc = ProjectService(session)
    svc.add_project("JobFlow AI", technologies=["Python"])
    session.commit()
    svc.add_project("JobFlow AI", technologies=["Python", "SQLite"])
    session.commit()
    assert session.query(Project).count() == 1
    p = session.query(Project).one()
    assert p.technologies == ["Python", "SQLite"]


def test_add_project_empty_name(session):
    svc = ProjectService(session)
    with pytest.raises(ProfileError):
        svc.add_project("  ")


def test_add_project_invalid_date(session):
    svc = ProjectService(session)
    with pytest.raises(ProfileError):
        svc.add_project("X", start_date="2025/01/01")


def test_add_project_start_after_end(session):
    svc = ProjectService(session)
    with pytest.raises(ProfileError):
        svc.add_project("X", start_date="2025-12-01", end_date="2025-01-01")


def test_remove_project(session):
    svc = ProjectService(session)
    svc.add_project("X")
    session.commit()
    assert svc.remove_project("X") is True
    session.commit()
    assert svc.remove_project("X") is False


def test_clear_projects(session):
    svc = ProjectService(session)
    svc.add_project("A")
    svc.add_project("B")
    session.commit()
    assert svc.clear() == 2
    session.commit()
    assert svc.list_projects() == []


# ---------------------------------------------------------------- cascade

def test_profile_reset_cascades_skills_and_projects(session):
    ProfileService(session).ensure_profile()
    SkillService(session).add_skill("Python")
    ProjectService(session).add_project("X")
    session.commit()
    assert session.query(Skill).count() == 1
    assert session.query(Project).count() == 1

    ProfileService(session).reset(confirm=True)
    session.commit()

    assert session.query(Skill).count() == 0
    assert session.query(Project).count() == 0