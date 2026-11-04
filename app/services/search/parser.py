"""
Deterministic natural-language parser for job search queries.

Approach:
    1. Canonicalize the raw query.
    2. Match against controlled dictionaries in a fixed priority order:
         - ambiguous seniority+employment terms
         - title families (longest match first)
         - seniority aliases
         - employment type aliases
         - remote aliases
         - countries (before cities, so "remote in germany" -> Germany)
         - cities (which set the country implicitly)
         - date-posted phrases
         - skills (from the CV skill vocabulary)
    3. Each match consumes its span so overlapping matches don't duplicate.
    4. Return a JobFilters object.
"""

from __future__ import annotations

import re

from app.services.cv.skills import VOCABULARY as CV_SKILL_VOCABULARY
from app.services.search.filters import JobFilters
from app.services.search.vocabulary import (
    AMBIGUOUS_SENIORITY_AND_EMPLOYMENT,
    CITY_TO_COUNTRY,
    COUNTRY_ALIASES,
    DATE_POSTED_PHRASES,
    EMPLOYMENT_TYPE_ALIASES,
    REMOTE_ALIASES,
    SENIORITY_ALIASES,
    TITLE_FAMILIES,
)

_WS = re.compile(r"\s+")
_PUNCT_KEEP = re.compile(r"[^\w\s#+.\-]")


def _canonicalize(text: str) -> str:
    """Lowercase, remove most punctuation, collapse whitespace."""
    if not text:
        return ""
    s = text.lower()
    s = _PUNCT_KEEP.sub(" ", s)
    s = _WS.sub(" ", s)
    return s.strip()


def _find_and_consume(
    text: str,
    patterns: list[str],
) -> tuple[str | None, str]:
    """
    Find the longest matching pattern in `text` (case-insensitive,
    whole-word). If found, return (pattern, remaining_text_with_span_blanked).
    Otherwise return (None, text).
    """
    for pattern in sorted(patterns, key=len, reverse=True):
        pat = re.compile(rf"(?<!\w){re.escape(pattern)}(?!\w)")
        match = pat.search(text)
        if match:
            blanked = text[:match.start()] + " " * (match.end() - match.start()) + text[match.end():]
            return pattern, blanked
    return None, text


def _find_all(
    text: str,
    patterns: list[str],
) -> tuple[list[str], str]:
    """
    Find all matches of any pattern (whole-word, longest-first per position).
    Returns (matched_patterns_in_order, remaining_text).
    """
    found: list[str] = []
    remaining = text
    while True:
        pattern, remaining = _find_and_consume(remaining, patterns)
        if pattern is None:
            break
        found.append(pattern)
    return found, remaining


def _match_titles(text: str) -> tuple[list[str], str]:
    """
    Match title families. Returns (canonical_titles, remaining_text).
    Includes parent titles automatically.
    """
    matched_canonicals: list[str] = []

    variant_to_family: dict[str, tuple[str, tuple[str, ...]]] = {}
    for family in TITLE_FAMILIES:
        for variant in family.variants:
            variant_to_family[variant] = (family.canonical, family.parents)

    remaining = text
    while True:
        all_variants = list(variant_to_family.keys())
        match, new_remaining = _find_and_consume(remaining, all_variants)
        if match is None:
            break
        canonical, parents = variant_to_family[match]
        if canonical not in matched_canonicals:
            matched_canonicals.append(canonical)
        for parent in parents:
            if parent not in matched_canonicals:
                matched_canonicals.append(parent)
        remaining = new_remaining

    return matched_canonicals, remaining


def _match_from_aliases(
    text: str,
    alias_map: dict[str, str],
) -> tuple[list[str], str]:
    """
    Match aliases; return (list of canonical values, remaining text).
    Values are deduplicated preserving order.
    """
    keys = list(alias_map.keys())
    matched_surfaces, remaining = _find_all(text, keys)
    values: list[str] = []
    for surface in matched_surfaces:
        canonical = alias_map[surface]
        if canonical not in values:
            values.append(canonical)
    return values, remaining


def _match_single(text: str, alias_map: dict[str, str]) -> tuple[str | None, str]:
    """Match at most one alias; return (canonical, remaining)."""
    keys = list(alias_map.keys())
    match, remaining = _find_and_consume(text, keys)
    if match is None:
        return None, text
    return alias_map[match], remaining


def _match_cities(text: str) -> tuple[list[str], list[str], str]:
    """
    Match city names. Returns (cities, implied_countries, remaining).
    """
    keys = list(CITY_TO_COUNTRY.keys())
    matched_cities, remaining = _find_all(text, keys)
    cities: list[str] = []
    countries: list[str] = []
    for surface in matched_cities:
        display = " ".join(w.capitalize() for w in surface.split())
        if display not in cities:
            cities.append(display)
        country = CITY_TO_COUNTRY[surface]
        if country not in countries:
            countries.append(country)
    return cities, countries, remaining


def _match_skills(text: str) -> tuple[list[str], str]:
    """
    Match skills against the CV vocabulary.
    """
    surface_to_canonical: dict[str, str] = {}
    for name, _category, patterns in CV_SKILL_VOCABULARY:
        for p in patterns:
            surface_to_canonical[p.strip().lower()] = name

    surfaces, remaining = _find_all(text, list(surface_to_canonical.keys()))
    skills: list[str] = []
    for s in surfaces:
        canonical = surface_to_canonical[s]
        if canonical not in skills:
            skills.append(canonical)
    return skills, remaining


def parse_query(raw_query: str) -> JobFilters:
    """
    Parse a natural-language query into structured filters.
    """
    filters = JobFilters(raw_query=raw_query)
    if not raw_query or not raw_query.strip():
        return filters

    text = _canonicalize(raw_query)

    # 1. Titles (special because of family/parent semantics)
    titles, text = _match_titles(text)
    filters.titles = titles

    # 2. Ambiguous terms (seniority AND employment type simultaneously)
    amb_keys = list(AMBIGUOUS_SENIORITY_AND_EMPLOYMENT.keys())
    matched_amb, text = _find_all(text, amb_keys)
    for surface in matched_amb:
        sen, emp = AMBIGUOUS_SENIORITY_AND_EMPLOYMENT[surface]
        if sen not in filters.seniority:
            filters.seniority.append(sen)
        if emp not in filters.employment_types:
            filters.employment_types.append(emp)

    # 3. Seniority
    seniority, text = _match_from_aliases(text, SENIORITY_ALIASES)
    for s in seniority:
        if s not in filters.seniority:
            filters.seniority.append(s)

    # 4. Employment types
    emp_more, text = _match_from_aliases(text, EMPLOYMENT_TYPE_ALIASES)
    for e in emp_more:
        if e not in filters.employment_types:
            filters.employment_types.append(e)

    # 5. Remote preference
    remote, text = _match_single(text, REMOTE_ALIASES)
    filters.remote_preference = remote

    # 6. Countries
    countries, text = _match_from_aliases(text, COUNTRY_ALIASES)
    filters.countries = countries

    # 7. Cities (add implied countries)
    cities, implied_countries, text = _match_cities(text)
    filters.locations = cities
    for c in implied_countries:
        if c not in filters.countries:
            filters.countries.append(c)

    # 8. Date posted
    keys = list(DATE_POSTED_PHRASES.keys())
    matched_date, text = _find_and_consume(text, keys)
    if matched_date:
        filters.date_posted_within_days = DATE_POSTED_PHRASES[matched_date]

    # 9. Skills
    skills, text = _match_skills(text)
    filters.required_skills = skills

    return filters