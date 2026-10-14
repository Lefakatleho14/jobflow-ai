"""
Phase 5 tests: fuzzy similarity math, alias lookup, integration with import.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import Job, JobAlias
from app.services.jobs import JobImportService, content_hash
from app.services.jobs.fuzzy import (
    canonical,
    canonical_title,
    combined_similarity,
    companies_match,
    jaccard,
    levenshtein,
    levenshtein_ratio,
    location_similarity,
    sequence_ratio,
    strip_company_suffixes,
    strip_location_suffixes,
    title_similarity,
    tokens,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_fuzzy_"))
    db_file = tmp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
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


@pytest.fixture(autouse=True)
def reset_fuzzy_env(monkeypatch):
    """Ensure tests use predictable thresholds."""
    monkeypatch.setenv("FUZZY_MATCH_THRESHOLD", "0.82")
    monkeypatch.setenv("FUZZY_COMPANY_WINDOW_DAYS", "90")


# ---------------------------------------------------------------- primitives

def test_levenshtein_identical():
    assert levenshtein("abc", "abc") == 0


def test_levenshtein_known_distance():
    assert levenshtein("kitten", "sitting") == 3


def test_levenshtein_empty():
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_levenshtein_ratio_identical():
    assert levenshtein_ratio("abc", "abc") == 1.0


def test_levenshtein_ratio_range():
    r = levenshtein_ratio("abc", "xyz")
    assert 0.0 <= r <= 1.0
    assert r < 0.5


def test_sequence_ratio_identical():
    assert sequence_ratio("abc", "abc") == 1.0


def test_sequence_ratio_different():
    assert sequence_ratio("abc", "xyz") < 0.5


def test_jaccard_identical():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial():
    assert jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5


def test_jaccard_empty_both():
    assert jaccard(set(), set()) == 1.0


# ---------------------------------------------------------------- canonicalization

def test_canonical_lowercase_and_strip():
    assert canonical("  Hello, World!  ") == "hello world"


def test_canonical_punctuation_removed():
    assert canonical("C++ / Python, FastAPI.") == "c python fastapi"


def test_tokens_returns_set():
    assert tokens("Python FastAPI Python") == {"python", "fastapi"}


def test_strip_company_suffixes_inc():
    assert strip_company_suffixes("Acme Inc.") == "acme"


def test_strip_company_suffixes_multiple():
    assert strip_company_suffixes("Acme Holdings Ltd") == "acme"


def test_strip_company_suffixes_keeps_meaningful_words():
    assert strip_company_suffixes("Data Company Group") == "data"


def test_strip_location_suffixes_country_code():
    assert strip_location_suffixes("Johannesburg, ZA") == "johannesburg"


def test_strip_location_suffixes_full_country():
    assert strip_location_suffixes("Johannesburg, South Africa") == "johannesburg"


def test_strip_location_suffixes_no_suffix():
    assert strip_location_suffixes("Cape Town") == "cape town"


# ---------------------------------------------------------------- abbreviations

def test_canonical_title_expands_jr():
    assert canonical_title("Jr. Developer") == "junior developer"


def test_canonical_title_expands_sr():
    assert canonical_title("Sr. Engineer") == "senior engineer"


def test_title_similarity_jr_vs_junior():
    assert title_similarity("Jr. Python Developer", "Junior Python Developer") == 1.0


def test_title_similarity_sr_vs_senior():
    assert title_similarity("Sr. Backend Engineer", "Senior Backend Engineer") == 1.0


# ---------------------------------------------------------------- title similarity

def test_title_similarity_identical():
    assert title_similarity("Python Developer", "Python Developer") == 1.0


def test_title_similarity_case_insensitive():
    assert title_similarity("PYTHON DEVELOPER", "python developer") == 1.0


def test_title_similarity_abbreviation():
    score = title_similarity("Jr. Python Developer", "Junior Python Developer")
    assert score > 0.7


def test_title_similarity_completely_different():
    score = title_similarity("Python Developer", "Marketing Manager")
    assert score < 0.3


def test_title_similarity_empty_both():
    assert title_similarity(None, None) == 1.0
    assert title_similarity("", "") == 1.0


def test_title_similarity_one_empty():
    assert title_similarity("Python Developer", "") == 0.0


# ---------------------------------------------------------------- location similarity

def test_location_similarity_identical():
    assert location_similarity("Johannesburg", "Johannesburg") == 1.0


def test_location_similarity_country_code_ignored():
    assert location_similarity("Johannesburg, ZA", "Johannesburg, South Africa") == 1.0


def test_location_similarity_both_empty():
    assert location_similarity(None, None) == 1.0


def test_location_similarity_one_empty():
    assert location_similarity("Johannesburg", None) == 0.5


def test_location_similarity_different_cities():
    assert location_similarity("Johannesburg", "Cape Town") == 0.0


# ---------------------------------------------------------------- combined

def test_combined_similarity_weights_validated():
    with pytest.raises(ValueError):
        combined_similarity(
            title_a="a", title_b="a",
            location_a="x", location_b="x",
            title_weight=0.5, location_weight=0.4,
        )


def test_combined_similarity_perfect():
    combined, t, l = combined_similarity(
        title_a="Python Developer",
        title_b="Python Developer",
        location_a="Johannesburg, ZA",
        location_b="Johannesburg, South Africa",
    )
    assert combined == 1.0
    assert t == 1.0
    assert l == 1.0


def test_combined_similarity_reasonable_match():
    combined, t, l = combined_similarity(
        title_a="Jr. Python Developer",
        title_b="Junior Python Developer",
        location_a="Johannesburg, ZA",
        location_b="Johannesburg",
    )
    assert combined > 0.9
    assert t > 0.9
    assert l == 1.0


# ---------------------------------------------------------------- company matching

def test_companies_match_identical():
    assert companies_match("Acme", "Acme")


def test_companies_match_with_suffix():
    assert companies_match("Acme Inc", "Acme Ltd")


def test_companies_match_different():
    assert not companies_match("Acme", "Beta")


def test_companies_match_one_empty():
    assert not companies_match("Acme", "")
    assert not companies_match("", "Acme")


# ---------------------------------------------------------------- integration helpers

def _payload(title, company, location, **extra):
    p = {
        "title": title,
        "company": company,
        "location": location,
        "description": "A job.",
        "source": "manual",
    }
    p.update(extra)
    return p


# ---------------------------------------------------------------- integration tests

def test_fuzzy_alias_created_on_near_duplicate(session):
    """A near-duplicate with a different hash should create a JobAlias, not a Job."""
    service = JobImportService(session)

    r1 = service.import_job(_payload("Junior Python Developer", "Acme Inc", "Johannesburg"))
    session.commit()
    assert r1.created is True
    assert session.query(Job).count() == 1

    r2 = service.import_job(_payload("Jr. Python Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    assert r2.created is False
    assert r2.reason == "fuzzy_alias"
    assert r2.alias_similarity > 0.82
    assert session.query(Job).count() == 1
    assert session.query(JobAlias).count() == 1
    alias = session.query(JobAlias).one()
    assert alias.job_id == r1.job.id
    assert alias.alias_title == "Jr. Python Developer"


def test_fuzzy_alias_idempotent(session):
    """Importing the same near-duplicate twice creates only one alias."""
    service = JobImportService(session)

    service.import_job(_payload("Junior Python Developer", "Acme Inc", "Johannesburg"))
    session.commit()

    service.import_job(_payload("Jr. Python Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    service.import_job(_payload("Jr. Python Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    assert session.query(Job).count() == 1
    assert session.query(JobAlias).count() == 1


def test_different_company_not_fuzzy_matched(session):
    """Same title, different company → fuzzy must NOT trigger."""
    service = JobImportService(session)

    service.import_job(_payload("Python Developer", "Acme Inc", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Python Developer", "Beta Ltd", "Johannesburg"))
    session.commit()

    assert r.created is True
    assert session.query(Job).count() == 2
    assert session.query(JobAlias).count() == 0


def test_different_location_not_fuzzy_matched(session):
    """Same title, same company, vastly different location → fuzzy should not trigger."""
    service = JobImportService(session)

    service.import_job(_payload("Python Developer", "Acme", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Python Developer", "Acme", "Tokyo"))
    session.commit()

    assert r.created is True
    assert session.query(Job).count() == 2
    assert session.query(JobAlias).count() == 0


def test_fuzzy_respects_threshold(session, monkeypatch):
    """
    With a threshold above what any real pair can reach, fuzzy must NOT fire.
    Uses a moderate-match pair (seniority word added) so the score is
    meaningfully below 1.0 even after abbreviation expansion.
    """
    monkeypatch.setenv("FUZZY_MATCH_THRESHOLD", "0.999")

    service = JobImportService(session)
    service.import_job(_payload("Software Developer", "Acme Inc", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Senior Software Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    # Threshold 0.999 is unreachable for this pair → job inserted, no alias
    assert r.created is True
    assert r.reason == "created"
    assert session.query(JobAlias).count() == 0
    assert session.query(Job).count() == 2


def test_fuzzy_aliases_seniority_variant_at_default_threshold(session):
    """
    'Software Developer' vs 'Senior Software Developer' is a boundary case:
    the combined similarity (~0.82) sits right at the default threshold.
    At the default, the alias fires — the user should review near-threshold
    matches themselves. This is the human-in-the-loop design.
    """
    service = JobImportService(session)
    service.import_job(_payload("Software Developer", "Acme Inc", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Senior Software Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    # Near-threshold pair → alias recorded for human review
    assert r.created is False
    assert r.reason == "fuzzy_alias"
    assert 0.80 <= r.alias_similarity <= 0.85
    assert session.query(JobAlias).count() == 1
    assert session.query(Job).count() == 1


def test_no_alias_for_clearly_different_roles(session):
    """
    Same company, same location, genuinely different roles →
    combined similarity well below threshold → new job inserted.
    """
    service = JobImportService(session)
    service.import_job(_payload("Software Developer", "Acme", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Marketing Manager", "Acme", "Johannesburg"))
    session.commit()

    assert r.created is True
    assert r.reason == "created"
    assert session.query(JobAlias).count() == 0
    assert session.query(Job).count() == 2


def test_fuzzy_does_not_override_deterministic(session):
    """A content-hash match should return duplicate, not fuzzy_alias."""
    service = JobImportService(session)

    service.import_job(_payload("Python Developer", "Acme", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Python Developer", "Acme", "Johannesburg"))
    session.commit()

    assert r.reason == "duplicate"
    assert session.query(JobAlias).count() == 0


def test_alias_has_similarity_fields_populated(session):
    service = JobImportService(session)
    service.import_job(_payload("Junior Python Developer", "Acme Inc", "Johannesburg"))
    session.commit()
    service.import_job(_payload("Jr. Python Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    alias = session.query(JobAlias).one()
    assert alias.similarity >= 0.82
    assert 0.0 <= alias.title_similarity <= 1.0
    assert 0.0 <= alias.location_similarity <= 1.0
    assert alias.reason is not None
    assert "combined" in alias.reason


def test_alias_cascade_delete_with_job(session):
    service = JobImportService(session)
    r = service.import_job(_payload("Junior Python Developer", "Acme Inc", "Johannesburg"))
    session.commit()
    service.import_job(_payload("Jr. Python Developer", "Acme", "Johannesburg, ZA"))
    session.commit()

    assert session.query(JobAlias).count() == 1
    session.delete(r.job)
    session.commit()
    assert session.query(JobAlias).count() == 0


def test_fuzzy_fires_for_pure_punctuation_difference(session):
    """
    'Sr. Python Developer' vs 'Senior Python Developer' are the same job.
    Under abbreviation expansion, similarity = 1.0 → alias fires.
    """
    service = JobImportService(session)
    service.import_job(_payload("Sr. Python Developer", "Acme", "Johannesburg"))
    session.commit()

    r = service.import_job(_payload("Senior Python Developer", "Acme", "Johannesburg"))
    session.commit()

    assert r.created is False
    assert r.reason == "fuzzy_alias"
    assert session.query(JobAlias).count() == 1