"""
Pydantic schema for LLM-extracted job requirements.

The LLM is non-deterministic — it may return strings where we expect
ints, single strings where we expect lists, or `null` where we expect
empty lists. This module defines the canonical shape and provides
repair functions for the most common malformations.

Repair philosophy:
    * Fix what can be fixed unambiguously.
    * Reject what cannot be fixed confidently.
    * Never fabricate: if a field is absent, use null/[] — do not invent.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---- Repair helpers ----

_LEADING_INT = re.compile(r"\b(\d+)")


def _repair_string_list(value: Any) -> list[str]:
    """
    Normalize a value into a list of clean strings.
    * None / "" -> []
    * "Python, SQL" -> ["Python", "SQL"]
    * ["Python", None, "  SQL  "] -> ["Python", "SQL"]
    """
    if value is None:
        return []
    if isinstance(value, str):
        # Single string: split on commas.
        if not value.strip():
            return []
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        return [str(s).strip() for s in value if s is not None and str(s).strip()]
    return []


def _repair_experience_years(value: Any) -> int | None:
    """
    Coerce a variety of inputs to int-or-None.
    * None / "" -> None
    * 3 -> 3
    * "3" -> 3
    * "3-5" / "3-5 years" / "3+ years" -> 3
    * "three" -> None (can't guess)
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        m = _LEADING_INT.search(value)
        if m:
            n = int(m.group(1))
            return n if n >= 0 else None
        return None
    return None


# ---- Canonical schema ----

VALID_SENIORITY = {
    "intern", "student", "graduate", "entry", "junior",
    "mid", "senior", "lead", "manager", "unknown",
}


class JobRequirementSchema(BaseModel):
    """
    Canonical shape for LLM-extracted job requirements.

    All fields have sensible defaults so a partially-valid response
    (e.g. missing `soft_skills`) is still usable.
    """
    model_config = ConfigDict(extra="ignore")  # drop unknown keys silently

    title: Optional[str] = None
    seniority: str = "unknown"
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    devops: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experience_years: Optional[int] = None
    salary: Optional[str] = None
    mandatory_requirements: List[str] = Field(default_factory=list)
    preferred_requirements: List[str] = Field(default_factory=list)

    # ---- Field-level repairs ----

    @field_validator("title", "salary", mode="before")
    @classmethod
    def _clean_optional_str(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator(
        "languages", "frameworks", "databases", "cloud", "devops",
        "soft_skills", "education",
        "mandatory_requirements", "preferred_requirements",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, v: Any) -> Any:
        return _repair_string_list(v)

    @field_validator("experience_years", mode="before")
    @classmethod
    def _coerce_years(cls, v: Any) -> Any:
        return _repair_experience_years(v)

    @field_validator("seniority", mode="before")
    @classmethod
    def _coerce_seniority(cls, v: Any) -> str:
        if v is None:
            return "unknown"
        s = str(v).strip().lower()
        return s if s in VALID_SENIORITY else "unknown"

    # ---- Model-level cross-field validation ----

    @model_validator(mode="after")
    def _check_consistency(self) -> "JobRequirementSchema":
        # Deduplicate lists preserving order, and remove empties.
        for field in (
            "languages", "frameworks", "databases", "cloud", "devops",
            "soft_skills", "education",
            "mandatory_requirements", "preferred_requirements",
        ):
            values: list[str] = getattr(self, field)
            seen: set[str] = set()
            deduped: list[str] = []
            for v in values:
                key = v.lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(v)
            setattr(self, field, deduped)

        # Salary: ensure string or None.
        if self.salary is not None and not isinstance(self.salary, str):
            self.salary = str(self.salary)

        return self


def parse_and_validate(raw: dict) -> tuple[JobRequirementSchema | None, list[str]]:
    """
    Parse an LLM response dict into a validated schema.

    Returns (schema_or_None, list_of_problems).
    If validation fails, schema is None and problems contains the reasons.
    """
    problems: list[str] = []

    if not isinstance(raw, dict):
        return None, [f"Expected dict, got {type(raw).__name__}"]

    try:
        model = JobRequirementSchema.model_validate(raw)
    except Exception as exc:
        return None, [f"Validation failed: {exc}"]

    return model, problems