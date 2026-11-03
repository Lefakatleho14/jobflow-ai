"""
Phase 7 tests: CV validation, extraction, skill matching, apply logic.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Skill
from app.services.cv import (
    CVError,
    CVExtractionError,
    CVImportService,
    CVValidationError,
    MAX_FILE_BYTES,
    extract_skills,
    extract_text,
    validate_file,
)
from app.services.profile import ProfileService, ProjectService, SkillService

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_DOCX = FIXTURES / "sample_cv.docx"


@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_cv_"))
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
def sample_docx(tmp_path: Path) -> Path:
    """Copy the fixture DOCX into a temp dir so tests don't mutate the original."""
    if not SAMPLE_DOCX.exists():
        pytest.skip("sample_cv.docx fixture missing — run tests/fixtures/make_fixture.py")
    dest = tmp_path / "cv.docx"
    shutil.copyfile(SAMPLE_DOCX, dest)
    return dest


# ---------------------------------------------------------------- validation

def test_validate_rejects_missing_file(tmp_path):
    with pytest.raises(CVValidationError):
        validate_file(tmp_path / "nope.pdf")


def test_validate_rejects_wrong_extension(tmp_path):
    p = tmp_path / "cv.txt"
    p.write_bytes(b"hello")
    with pytest.raises(CVValidationError):
        validate_file(p)


def test_validate_rejects_empty_file(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(b"")
    with pytest.raises(CVValidationError):
        validate_file(p)


def test_validate_rejects_oversize(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(b"%PDF" + b"\x00" * (MAX_FILE_BYTES + 1))
    with pytest.raises(CVValidationError):
        validate_file(p)


def test_validate_rejects_pdf_that_is_not_pdf(tmp_path):
    p = tmp_path / "cv.pdf"
    p.write_bytes(b"GIF89a-fake-pdf")
    with pytest.raises(CVValidationError):
        validate_file(p)


def test_validate_accepts_valid_docx(sample_docx):
    validate_file(sample_docx)  # should not raise


# ---------------------------------------------------------------- text extraction

def test_extract_text_docx(sample_docx):
    text = extract_text(sample_docx)
    assert "Katleho" in text
    assert "Python" in text
    assert "FastAPI" in text


def test_extract_text_unsupported_extension(tmp_path):
    p = tmp_path / "cv.rtf"
    p.write_bytes(b"whatever")
    with pytest.raises(CVExtractionError):
        extract_text(p)


# ---------------------------------------------------------------- skill extraction

def test_extract_skills_finds_python():
    skills = extract_skills("I use Python every day.")
    names = {s.name for s in skills}
    assert "Python" in names


def test_extract_skills_does_not_match_java_in_javascript():
    skills = extract_skills("I write JavaScript code.")
    names = {s.name for s in skills}
    assert "JavaScript" in names
    assert "Java" not in names


def test_extract_skills_multiple():
    skills = extract_skills("Python, FastAPI, and Docker.")
    names = {s.name for s in skills}
    assert {"Python", "FastAPI", "Docker"}.issubset(names)


def test_extract_skills_case_insensitive():
    skills = extract_skills("python and FASTAPI")
    names = {s.name for s in skills}
    assert {"Python", "FastAPI"}.issubset(names)


def test_extract_skills_no_matches():
    skills = extract_skills("I like long walks on the beach.")
    assert skills == []


# ---------------------------------------------------------------- proposal

def test_propose_returns_populated_proposal(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    assert proposal.source_filename == "cv.docx"
    assert proposal.stored_filename is not None
    names = {s.name for s in proposal.skills}
    assert {"Python", "FastAPI", "SQLite", "Docker"}.issubset(names)
    assert len(proposal.education) >= 1
    assert any("BSc" in e.line for e in proposal.education)


def test_propose_does_not_touch_profile(session, sample_docx):
    svc = CVImportService(session)
    svc.propose(sample_docx)
    session.commit()
    # No skills should exist yet
    assert session.query(Skill).count() == 0


# ---------------------------------------------------------------- apply

def test_apply_requires_confirm(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    with pytest.raises(CVError):
        svc.apply(proposal)


def test_apply_adds_skills(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    summary = svc.apply(proposal, confirm=True)
    session.commit()

    assert summary["added_skills"] > 0
    skill_svc = SkillService(session)
    names = {s.name for s in skill_svc.list_skills()}
    assert "Python" in names
    assert "FastAPI" in names


def test_apply_is_idempotent(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    svc.apply(proposal, confirm=True)
    session.commit()
    count_after_first = session.query(Skill).count()

    proposal2 = svc.propose(sample_docx)
    svc.apply(proposal2, confirm=True)
    session.commit()
    count_after_second = session.query(Skill).count()

    assert count_after_first == count_after_second


def test_apply_sets_education_when_empty(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    svc.apply(proposal, confirm=True)
    session.commit()

    profile = ProfileService(session).get_profile()
    assert profile.education is not None
    assert "BSc" in profile.education or "Bachelor" in profile.education


def test_apply_does_not_overwrite_existing_education(session, sample_docx):
    profile_svc = ProfileService(session)
    profile_svc.update_scalar("education", "My Existing Education")
    session.commit()

    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    svc.apply(proposal, confirm=True)
    session.commit()

    profile = profile_svc.get_profile()
    assert profile.education == "My Existing Education"


def test_apply_adds_projects(session, sample_docx):
    svc = CVImportService(session)
    proposal = svc.propose(sample_docx)
    summary = svc.apply(proposal, confirm=True)
    session.commit()

    assert summary["added_projects"] >= 1
    project_svc = ProjectService(session)
    names = {p.name for p in project_svc.list_projects()}
    assert "JobFlow AI" in names