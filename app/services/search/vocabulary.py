"""
Controlled vocabulary for natural-language job search.

Design notes:
  * Everything here is deterministic and human-curated.
  * Every entry maps ONE surface form to a CANONICAL form used downstream.
  * We do not attempt exhaustive coverage — we cover the 95% case.
  * Extending the vocabulary is a code change with tests, not config.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TitleFamily:
    """A canonical job title family with its surface variants."""
    canonical: str
    variants: tuple[str, ...]      # matched case-insensitively, whole words
    parents: tuple[str, ...] = ()  # canonical names this family also satisfies


# Canonical job title families.
TITLE_FAMILIES: list[TitleFamily] = [
    TitleFamily(
        canonical="Software Developer",
        variants=("software developer", "software dev", "swe",
                  "software engineer", "developer"),
    ),
    TitleFamily(
        canonical="Python Developer",
        variants=("python developer", "python dev", "python engineer"),
        parents=("Software Developer",),
    ),
    TitleFamily(
        canonical="Backend Developer",
        variants=("backend developer", "back-end developer", "back end developer",
                  "backend dev", "back end dev"),
        parents=("Software Developer",),
    ),
    TitleFamily(
        canonical="Frontend Developer",
        variants=("frontend developer", "front-end developer", "front end developer",
                  "frontend dev", "front end dev"),
        parents=("Software Developer",),
    ),
    TitleFamily(
        canonical="Full Stack Developer",
        variants=("full stack developer", "fullstack developer", "full-stack developer",
                  "full stack", "fullstack", "full-stack"),
        parents=("Software Developer",),
    ),
    TitleFamily(
        canonical="Data Engineer",
        variants=("data engineer", "data dev"),
    ),
    TitleFamily(
        canonical="DevOps Engineer",
        variants=("devops engineer", "devops", "sre", "site reliability engineer"),
    ),
    TitleFamily(
        canonical="Data Scientist",
        variants=("data scientist", "data science"),
    ),
    TitleFamily(
        canonical="ML Engineer",
        variants=("machine learning engineer", "ml engineer"),
    ),
    TitleFamily(
        canonical="QA Engineer",
        variants=("qa engineer", "quality assurance", "tester"),
    ),
    TitleFamily(
        canonical="Product Manager",
        variants=("product manager",),
    ),
    TitleFamily(
        canonical="Android Developer",
        variants=("android developer", "android dev"),
        parents=("Mobile Developer",),
    ),
    TitleFamily(
        canonical="iOS Developer",
        variants=("ios developer", "ios dev"),
        parents=("Mobile Developer",),
    ),
    TitleFamily(
        canonical="Mobile Developer",
        variants=("mobile developer", "mobile dev"),
    ),
]


# Seniority aliases → canonical Seniority enum value.
SENIORITY_ALIASES: dict[str, str] = {
    "intern": "intern", "internship": "intern",
    "student": "student",
    "graduate": "graduate", "grad": "graduate",
    "entry": "entry", "entry level": "entry", "entry-level": "entry",
    "junior": "junior", "jr": "junior",
    "mid": "mid", "mid level": "mid", "mid-level": "mid", "intermediate": "mid",
    "senior": "senior", "sr": "senior",
    "lead": "lead", "tech lead": "lead",
    "manager": "manager",
}


# Employment type aliases → canonical EmploymentType enum value.
EMPLOYMENT_TYPE_ALIASES: dict[str, str] = {
    "permanent": "permanent", "full time": "permanent", "full-time": "permanent",
    "contract": "contract", "contractor": "contract",
    "temporary": "temporary", "temp": "temporary",
    "internship": "internship", "intern": "internship",
    "learnership": "learnership",
    "graduate programme": "graduate", "graduate program": "graduate",
    "apprenticeship": "apprenticeship",
    "part time": "part_time", "part-time": "part_time",
    "freelance": "freelance",
}


# Terms that legitimately mean both a seniority level AND an employment type.
# When matched, both fields are populated.
AMBIGUOUS_SENIORITY_AND_EMPLOYMENT: dict[str, tuple[str, str]] = {
    "internship": ("intern", "internship"),
    "intern": ("intern", "internship"),
    "graduate programme": ("graduate", "graduate"),
    "graduate program": ("graduate", "graduate"),
    "graduate": ("graduate", "graduate"),
}


# Remote preference aliases → one of: remote, hybrid, onsite.
REMOTE_ALIASES: dict[str, str] = {
    "remote": "remote", "fully remote": "remote", "100% remote": "remote",
    "work from home": "remote", "wfh": "remote", "telecommute": "remote",
    "hybrid": "hybrid", "partially remote": "hybrid", "flexible": "hybrid",
    "onsite": "onsite", "on-site": "onsite", "on site": "onsite",
    "in office": "onsite", "in-office": "onsite",
}


# Country aliases → canonical country name.
COUNTRY_ALIASES: dict[str, str] = {
    "south africa": "South Africa", "za": "South Africa", "rsa": "South Africa",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "gb": "United Kingdom", "england": "United Kingdom",
    "germany": "Germany", "de": "Germany",
    "netherlands": "Netherlands", "nl": "Netherlands", "holland": "Netherlands",
    "united states": "United States", "us": "United States",
    "usa": "United States", "america": "United States",
    "canada": "Canada", "ca": "Canada",
    "australia": "Australia", "au": "Australia",
    "new zealand": "New Zealand", "nz": "New Zealand",
    "ireland": "Ireland", "ie": "Ireland",
    "india": "India", "in": "India",
    "kenya": "Kenya", "ke": "Kenya",
    "nigeria": "Nigeria", "ng": "Nigeria",
}


# City → country mapping.
CITY_TO_COUNTRY: dict[str, str] = {
    "johannesburg": "South Africa",
    "joburg": "South Africa",
    "sandton": "South Africa",
    "midrand": "South Africa",
    "centurion": "South Africa",
    "pretoria": "South Africa",
    "cape town": "South Africa",
    "durban": "South Africa",
    "port elizabeth": "South Africa",
    "gqeberha": "South Africa",
    "bloemfontein": "South Africa",
    "east london": "South Africa",
    "london": "United Kingdom",
    "manchester": "United Kingdom",
    "berlin": "Germany",
    "munich": "Germany",
    "amsterdam": "Netherlands",
    "dublin": "Ireland",
    "new york": "United States",
    "san francisco": "United States",
    "toronto": "Canada",
    "sydney": "Australia",
    "melbourne": "Australia",
    "nairobi": "Kenya",
    "lagos": "Nigeria",
    "bangalore": "India",
}


# Date-posted phrases → max age in days.
DATE_POSTED_PHRASES: dict[str, int] = {
    "today": 1,
    "last 24 hours": 1,
    "yesterday": 2,
    "last 3 days": 3,
    "last week": 7,
    "last 7 days": 7,
    "this week": 7,
    "last 14 days": 14,
    "last two weeks": 14,
    "last 30 days": 30,
    "last month": 30,
    "this month": 30,
}