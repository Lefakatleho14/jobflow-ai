"""
Phase 7.5 tests: new normalizer fields (employment_type, seniority, country).
"""

from __future__ import annotations

import pytest

from app.services.jobs.normalizer import (
    normalize_employment_type,
    normalize_seniority,
    normalize_job_fields,
)


@pytest.mark.parametrize("raw,expected", [
    ("Permanent", "permanent"),
    ("Full-time", "permanent"),
    ("Contract", "contract"),
    ("Internship", "internship"),
    ("Graduate Programme", "graduate"),
    ("Part-time", "part_time"),
    ("Freelance", "freelance"),
    ("nonsense", "unknown"),
    (None, "unknown"),
])
def test_employment_type(raw, expected):
    assert normalize_employment_type(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Junior", "junior"),
    ("Jr", "junior"),
    ("Senior", "senior"),
    ("Mid-level", "mid"),
    ("Lead", "lead"),
    ("Graduate", "graduate"),
    ("Internship", "intern"),
    ("nonsense", "unknown"),
    (None, "unknown"),
])
def test_seniority(raw, expected):
    assert normalize_seniority(raw) == expected


def test_normalize_job_fields_includes_new_fields():
    result = normalize_job_fields({
        "title": "Junior Python Developer",
        "company": "Acme",
        "country": "South Africa",
        "employment_type": "Permanent",
        "seniority": "Junior",
    })
    assert result["country"] == "South Africa"
    assert result["employment_type"] == "permanent"
    assert result["seniority"] == "junior"
    assert result["availability_status"] == "unverified"
    assert result["date_posted_status"] == "unknown"