"""
Phase 11 tests: skill classification.
"""

from __future__ import annotations

import pytest

from app.services.matching.skill_classifier import (
    SkillMatch,
    classify_skill,
)


def _classify(required: str, **profile):
    """Helper: classify against a single profile skill."""
    defaults = dict(
        profile_skills=[], profile_frameworks=[], profile_languages=[],
        profile_databases=[], profile_cloud=[], profile_devops=[],
        profile_tools=[],
    )
    defaults.update(profile)
    return classify_skill(required, **defaults)


# ---------------------------------------------------------------- strong

def test_exact_match_strong():
    result = _classify("Python", profile_languages=["Python"])
    assert result.status == "strong"


def test_case_insensitive_match_strong():
    result = _classify("python", profile_languages=["PYTHON"])
    assert result.status == "strong"


def test_strong_via_skill_table():
    result = _classify("FastAPI", profile_skills=["FastAPI"])
    assert result.status == "strong"


# ---------------------------------------------------------------- partial (synonym)

def test_synonym_js_javascript_partial():
    result = _classify("JavaScript", profile_languages=["JS"])
    assert result.status == "partial"


def test_synonym_postgresql_partial():
    result = _classify("PostgreSQL", profile_databases=["Postgres"])
    assert result.status == "partial"


def test_synonym_k8s_partial():
    result = _classify("Kubernetes", profile_devops=["K8s"])
    assert result.status == "partial"


# ---------------------------------------------------------------- partial (implication)

def test_fastapi_implies_python():
    result = _classify("Python", profile_frameworks=["FastAPI"])
    assert result.status == "partial"


def test_react_implies_javascript():
    result = _classify("JavaScript", profile_frameworks=["React"])
    assert result.status == "partial"


def test_spring_boot_implies_java():
    result = _classify("Java", profile_frameworks=["Spring Boot"])
    assert result.status == "partial"


def test_docker_implies_devops():
    result = _classify("DevOps", profile_tools=["Docker"])
    assert result.status == "partial"


# ---------------------------------------------------------------- missing

def test_no_match_missing():
    result = _classify("Rust", profile_languages=["Python"])
    assert result.status == "missing"


def test_empty_required_missing():
    result = _classify("", profile_languages=["Python"])
    assert result.status == "missing"