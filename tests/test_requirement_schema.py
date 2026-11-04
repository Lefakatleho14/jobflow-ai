"""
Phase 10 tests: Pydantic schema validation and repair.
"""

from __future__ import annotations

import pytest

from app.services.jobs.requirement_schema import (
    JobRequirementSchema,
    parse_and_validate,
)


# ---------------------------------------------------------------- happy path

def test_minimal_valid_input():
    schema, problems = parse_and_validate({"title": "Dev"})
    assert schema is not None
    assert problems == []
    assert schema.title == "Dev"
    assert schema.seniority == "unknown"
    assert schema.languages == []


def test_full_valid_input():
    raw = {
        "title": "Junior Python Developer",
        "seniority": "junior",
        "languages": ["Python", "SQL"],
        "frameworks": ["FastAPI"],
        "databases": ["PostgreSQL"],
        "cloud": ["AWS"],
        "devops": ["Docker"],
        "soft_skills": ["communication"],
        "education": ["BSc Computer Science"],
        "experience_years": 2,
        "salary": "R300,000",
        "mandatory_requirements": ["Python"],
        "preferred_requirements": ["Docker"],
    }
    schema, problems = parse_and_validate(raw)
    assert schema is not None
    assert problems == []
    assert schema.languages == ["Python", "SQL"]
    assert schema.experience_years == 2


# ---------------------------------------------------------------- repairs

def test_string_where_list_expected():
    schema, _ = parse_and_validate({"languages": "Python, SQL, FastAPI"})
    assert schema.languages == ["Python", "SQL", "FastAPI"]


def test_null_where_list_expected():
    schema, _ = parse_and_validate({"languages": None})
    assert schema.languages == []


def test_list_with_nulls_and_whitespace():
    schema, _ = parse_and_validate({"languages": ["Python", None, "  SQL  "]})
    assert schema.languages == ["Python", "SQL"]


def test_experience_years_string_number():
    schema, _ = parse_and_validate({"experience_years": "3"})
    assert schema.experience_years == 3


def test_experience_years_range_string():
    schema, _ = parse_and_validate({"experience_years": "3-5 years"})
    assert schema.experience_years == 3


def test_experience_years_plus_suffix():
    schema, _ = parse_and_validate({"experience_years": "5+"})
    assert schema.experience_years == 5


def test_experience_years_word_returns_none():
    schema, _ = parse_and_validate({"experience_years": "three"})
    assert schema.experience_years is None


def test_invalid_seniority_becomes_unknown():
    schema, _ = parse_and_validate({"seniority": "principle"})
    assert schema.seniority == "unknown"


def test_uppercase_seniority_normalized():
    schema, _ = parse_and_validate({"seniority": "JUNIOR"})
    assert schema.seniority == "junior"


def test_title_whitespace_stripped():
    schema, _ = parse_and_validate({"title": "  Dev  "})
    assert schema.title == "Dev"


def test_empty_title_becomes_none():
    schema, _ = parse_and_validate({"title": "   "})
    assert schema.title is None


def test_extra_fields_dropped():
    schema, _ = parse_and_validate({"title": "Dev", "unexpected_field": "xyz"})
    assert schema is not None
    assert not hasattr(schema, "unexpected_field")


def test_duplicate_list_items_deduplicated():
    schema, _ = parse_and_validate({
        "languages": ["Python", "python", "SQL"]
    })
    assert schema.languages == ["Python", "SQL"]


def test_salary_as_non_string_coerced():
    schema, _ = parse_and_validate({"salary": 300000})
    assert schema.salary == "300000"


# ---------------------------------------------------------------- failures

def test_non_dict_input_returns_none():
    schema, problems = parse_and_validate("not a dict")
    assert schema is None
    assert any("dict" in p.lower() for p in problems)


def test_none_input_returns_none():
    schema, problems = parse_and_validate(None)
    assert schema is None