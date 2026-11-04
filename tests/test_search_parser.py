"""
Phase 8 tests: NL search parser, filters, query building.
"""

from __future__ import annotations

import pytest

from app.services.search import parse_query, build_query
from app.services.search.filters import JobFilters


# ---------------------------------------------------------------- basic parsing

def test_empty_query_returns_empty_filters():
    filters = parse_query("")
    assert filters.is_empty()
    assert filters.raw_query == ""


def test_whitespace_query_returns_empty_filters():
    filters = parse_query("   ")
    assert filters.is_empty()


def test_single_title():
    filters = parse_query("python developer")
    assert "Python Developer" in filters.titles
    assert "Software Developer" in filters.titles


def test_generic_developer_title():
    filters = parse_query("software developer")
    assert "Software Developer" in filters.titles


def test_multiple_titles():
    filters = parse_query("python or backend developer")
    assert "Software Developer" in filters.titles
    assert "Backend Developer" in filters.titles or "Python Developer" in filters.titles


# ---------------------------------------------------------------- seniority

@pytest.mark.parametrize("query,expected", [
    ("junior developer", "junior"),
    ("Jr developer", "junior"),
    ("senior engineer", "senior"),
    ("Sr engineer", "senior"),
    ("graduate developer", "graduate"),
    ("intern developer", "intern"),
    ("mid level dev", "mid"),
    ("lead developer", "lead"),
])
def test_seniority_matches(query, expected):
    filters = parse_query(query)
    assert expected in filters.seniority


# ---------------------------------------------------------------- employment types

@pytest.mark.parametrize("query,expected", [
    ("permanent role", "permanent"),
    ("full-time position", "permanent"),
    ("contract developer", "contract"),
    ("internship", "internship"),
    ("graduate programme", "graduate"),
    ("part-time dev", "part_time"),
])
def test_employment_types(query, expected):
    filters = parse_query(query)
    assert expected in filters.employment_types


def test_internship_sets_both_seniority_and_employment():
    filters = parse_query("internship")
    assert "intern" in filters.seniority
    assert "internship" in filters.employment_types


def test_graduate_programme_sets_both():
    filters = parse_query("graduate programme")
    assert "graduate" in filters.seniority
    assert "graduate" in filters.employment_types


# ---------------------------------------------------------------- remote

@pytest.mark.parametrize("query,expected", [
    ("remote developer", "remote"),
    ("work from home dev", "remote"),
    ("wfh role", "remote"),
    ("hybrid dev", "hybrid"),
    ("on-site role", "onsite"),
    ("in office developer", "onsite"),
])
def test_remote_preference(query, expected):
    filters = parse_query(query)
    assert filters.remote_preference == expected


# ---------------------------------------------------------------- locations

def test_city_implies_country():
    filters = parse_query("junior developer in Johannesburg")
    assert "Johannesburg" in filters.locations
    assert "South Africa" in filters.countries


def test_multiple_cities():
    filters = parse_query("developer Johannesburg or Cape Town")
    assert "Johannesburg" in filters.locations
    assert "Cape Town" in filters.locations


def test_explicit_country():
    filters = parse_query("senior developer in Germany")
    assert "Germany" in filters.countries
    assert not filters.locations


def test_country_alias():
    filters = parse_query("developer in UK")
    assert "United Kingdom" in filters.countries


# ---------------------------------------------------------------- skills

def test_skill_extraction():
    filters = parse_query("developer with Python and FastAPI")
    assert "Python" in filters.required_skills
    assert "FastAPI" in filters.required_skills


def test_skill_canonicalization():
    filters = parse_query("developer with python and sqlite")
    assert "Python" in filters.required_skills
    assert "SQLite" in filters.required_skills


# ---------------------------------------------------------------- dates

@pytest.mark.parametrize("query,expected", [
    ("dev jobs today", 1),
    ("roles last 24 hours", 1),
    ("dev jobs last week", 7),
    ("posted last 30 days", 30),
])
def test_date_posted_phrases(query, expected):
    filters = parse_query(query)
    assert filters.date_posted_within_days == expected


# ---------------------------------------------------------------- combined

def test_full_query_realistic():
    filters = parse_query(
        "junior python developer remote johannesburg last week"
    )
    assert "Python Developer" in filters.titles
    assert "junior" in filters.seniority
    assert filters.remote_preference == "remote"
    assert "Johannesburg" in filters.locations
    assert "South Africa" in filters.countries
    assert filters.date_posted_within_days == 7


def test_no_false_positives_on_random_text():
    filters = parse_query("I want a job where I can grow")
    assert filters.titles == []


# ---------------------------------------------------------------- query builder

def test_build_query_minimal():
    stmt = build_query(JobFilters())
    assert stmt is not None
    assert stmt.is_select


def test_build_query_with_title():
    filters = JobFilters(titles=["Python Developer"])
    stmt = build_query(filters)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "lower" in sql.lower() or "title" in sql.lower()
    assert "jobs" in sql


def test_build_query_with_country():
    filters = JobFilters(countries=["South Africa"])
    stmt = build_query(filters)
    assert stmt is not None


def test_build_query_respects_limit():
    stmt = build_query(JobFilters(titles=["Developer"]), limit=5)
    sql = str(stmt)
    assert "LIMIT" in sql.upper() or "limit" in sql.lower()


# ---------------------------------------------------------------- filters dataclass

def test_filters_empty():
    assert JobFilters().is_empty() is True


def test_filters_not_empty_with_title():
    assert JobFilters(titles=["Dev"]).is_empty() is False


def test_filters_to_dict():
    f = JobFilters(titles=["Dev"], countries=["ZA"])
    d = f.to_dict()
    assert d["titles"] == ["Dev"]
    assert d["countries"] == ["ZA"]
    assert d["raw_query"] == ""