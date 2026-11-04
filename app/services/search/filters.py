"""
JobFilters — the structured output of the natural-language parser.
This is what the query builder consumes to produce a SELECT.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobFilters:
    """Structured search criteria derived from a user query."""
    titles: list[str] = field(default_factory=list)          # canonical title families
    seniority: list[str] = field(default_factory=list)       # enum values
    employment_types: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)       # city names (normalized)
    countries: list[str] = field(default_factory=list)       # country names
    remote_preference: str | None = None                      # "remote" | "hybrid" | "onsite"
    required_skills: list[str] = field(default_factory=list)  # canonical skill names
    date_posted_within_days: int | None = None
    min_match_score: int | None = None
    raw_query: str = ""

    def is_empty(self) -> bool:
        return not any([
            self.titles, self.seniority, self.employment_types,
            self.locations, self.countries, self.remote_preference,
            self.required_skills, self.date_posted_within_days,
        ])

    def to_dict(self) -> dict:
        return {
            "titles": self.titles,
            "seniority": self.seniority,
            "employment_types": self.employment_types,
            "locations": self.locations,
            "countries": self.countries,
            "remote_preference": self.remote_preference,
            "required_skills": self.required_skills,
            "date_posted_within_days": self.date_posted_within_days,
            "min_match_score": self.min_match_score,
            "raw_query": self.raw_query,
        }