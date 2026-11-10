"""
Phase 11 tests: scoring engine.
"""

from __future__ import annotations

import pytest

from app.models import Job, JobRequirement, Profile, Project, Skill
from app.services.matching.scorer import score_job
from app.services.matching.weights import MatchingWeights


def _make_job(**kwargs):
    defaults = dict(
        title="Dev", company="Acme", seniority="junior",
        remote_status="hybrid", location="Johannesburg", country="South Africa",
    )
    defaults.update(kwargs)
    return Job(**defaults)


def _make_req(**kwargs):
    defaults = dict(
        seniority="junior",
        languages=["Python"],
        frameworks=["FastAPI"],
        databases=["SQLite"],
        cloud=[],
        devops=[],
        soft_skills=[],
        education=[],
        experience_years=None,
    )
    defaults.update(kwargs)
    req = JobRequirement(**defaults)
    for field in ("languages", "frameworks", "databases", "cloud", "devops",
                  "soft_skills", "education"):
        setattr(req, field, defaults.get(field, []))
    return req


def _make_profile(**kwargs):
    """Build a Profile. `degree` defaults to the same as `education`."""
    profile = Profile(
        name="Test",
        education=kwargs.get("education", "BSc Computer Science"),
        degree=kwargs.get("degree", kwargs.get("education", "BSc Computer Science")),
        remote_preference="any",
        minimum_match_score=70,
    )
    for field in ("languages", "frameworks", "databases", "cloud", "devops",
                  "tools", "certifications", "preferred_titles", "preferred_locations"):
        setattr(profile, field, kwargs.get(field, []))
    return profile


# ---------------------------------------------------------------- basic

def test_perfect_match_scores_high():
    job = _make_job()
    req = _make_req()
    job.requirement = req

    profile = _make_profile(
        languages=["Python"],
        frameworks=["FastAPI"],
        databases=["SQLite"],
    )
    profile.skills = [
        Skill(name="Python", category="language", proficiency="advanced", years=3),
        Skill(name="FastAPI", category="framework", proficiency="intermediate"),
        Skill(name="SQLite", category="database", proficiency="advanced"),
    ]
    profile.projects = [
        Project(name="X", technologies=["Python", "FastAPI", "SQLite"]),
    ]

    result = score_job(job, profile)
    assert result.score >= 80
    assert result.tier in ("high", "medium")
    assert "Python" in result.strong_matches


def test_missing_skills_scores_lower():
    job = _make_job()
    req = _make_req(
        languages=["Rust", "Go"],
        frameworks=["Actix"],
    )
    job.requirement = req

    profile = _make_profile(languages=["Python"], frameworks=["FastAPI"])
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    assert result.score < 70
    assert "Rust" in result.missing_skills
    assert "Go" in result.missing_skills


def test_no_requirement_returns_neutral():
    job = _make_job()
    job.requirement = None
    profile = _make_profile()

    result = score_job(job, profile)
    assert result.score == 50.0
    assert "No requirements" in result.explanation


def test_remote_job_location_boost():
    job = _make_job(remote_status="remote")
    job.requirement = _make_req()
    profile = _make_profile(languages=["Python"])

    result = score_job(job, profile)
    loc_dim = next(d for d in result.dimensions if d.name == "location")
    assert loc_dim.sub_score == 1.0


# ---------------------------------------------------------------- education

def test_education_mismatch():
    """A completely unrelated degree (Physics vs Computer Science) fails."""
    job = _make_job()
    job.requirement = _make_req(education=["MSc Computer Science"])
    profile = _make_profile(education="BSc Physics")
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    edu_dim = next(d for d in result.dimensions if d.name == "education")
    assert edu_dim.sub_score < 1.0
    # Either "field mismatch" or "degree level too low" is legitimate —
    # the education does not match in either dimension.
    assert (
        "field" in edu_dim.detail.lower()
        or "mismatch" in edu_dim.detail.lower()
        or "degree level" in edu_dim.detail.lower()
    )


def test_education_level_short_bsc_for_msc():
    """BSc does not satisfy an MSc requirement."""
    job = _make_job()
    job.requirement = _make_req(education=["MSc Computer Science"])
    profile = _make_profile(education="BSc Computer Science")
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    edu_dim = next(d for d in result.dimensions if d.name == "education")
    assert 0.4 <= edu_dim.sub_score <= 0.6


def test_education_software_engineering_satisfies_cs():
    """Software Engineering is a reasonable substitute for Computer Science."""
    job = _make_job()
    job.requirement = _make_req(education=["BSc Computer Science"])
    profile = _make_profile(education="BSc Software Engineering")
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    edu_dim = next(d for d in result.dimensions if d.name == "education")
    assert edu_dim.sub_score >= 0.9


def test_education_msc_satisfies_bsc_requirement():
    """A higher degree satisfies a lower requirement."""
    job = _make_job()
    job.requirement = _make_req(education=["BSc Computer Science"])
    profile = _make_profile(education="MSc Computer Science")
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    edu_dim = next(d for d in result.dimensions if d.name == "education")
    assert edu_dim.sub_score == 1.0


# ---------------------------------------------------------------- experience

def test_experience_sufficient():
    job = _make_job()
    job.requirement = _make_req(experience_years=2)
    profile = _make_profile(languages=["Python"])
    profile.skills = [Skill(name="Python", category="language", years=3)]

    result = score_job(job, profile)
    exp_dim = next(d for d in result.dimensions if d.name == "experience")
    assert exp_dim.sub_score == 1.0


def test_experience_insufficient():
    job = _make_job()
    job.requirement = _make_req(experience_years=5)
    profile = _make_profile(languages=["Python"])
    profile.skills = [Skill(name="Python", category="language", years=2)]

    result = score_job(job, profile)
    exp_dim = next(d for d in result.dimensions if d.name == "experience")
    assert 0 < exp_dim.sub_score < 1.0


# ---------------------------------------------------------------- explanation + weights

def test_explanation_is_populated():
    job = _make_job()
    job.requirement = _make_req()
    profile = _make_profile(languages=["Python"])
    profile.skills = [Skill(name="Python", category="language")]

    result = score_job(job, profile)
    assert result.explanation
    assert "Score" in result.explanation


def test_weights_validation():
    with pytest.raises(ValueError):
        MatchingWeights(technical=0.9, education=0.9).validate()


def test_weights_tier_threshold():
    w = MatchingWeights()  # default thresholds 85 / 70
    assert w.tier_for(90) == "high"
    assert w.tier_for(75) == "medium"
    assert w.tier_for(50) == "low"