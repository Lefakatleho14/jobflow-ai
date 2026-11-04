"""
Field-level normalization for job listings.

Rules are deterministic and idempotent. Running normalize on
already-normalized data must be a no-op.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# ---- Regexes (compiled once) ----
_WHITESPACE_RUN = re.compile(r"\s+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_TRAILING_PUNCT = re.compile(r"[,\-\.;:]+$")
_CRLF = re.compile(r"\r\n?")

# ---- Remote-status synonym map ----
_REMOTE_ALIASES = {
    "remote": "remote",
    "fully remote": "remote",
    "100% remote": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "telecommute": "remote",
    "hybrid": "hybrid",
    "partially remote": "hybrid",
    "flexible": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "in office": "onsite",
    "in-office": "onsite",
    "": "unknown",
    "unknown": "unknown",
    "n/a": "unknown",
}

# ---- Employment Type synonym map (Phase 7.5) ----
_EMPLOYMENT_TYPE_ALIASES = {
    "permanent": "permanent", "full time": "permanent", "full-time": "permanent",
    "contract": "contract", "contractor": "contract",
    "temporary": "temporary", "temp": "temporary",
    "internship": "internship", "intern": "internship",
    "learnership": "learnership",
    "graduate": "graduate", "graduate programme": "graduate",
    "apprenticeship": "apprenticeship",
    "part time": "part_time", "part-time": "part_time",
    "freelance": "freelance",
}

# ---- Seniority synonym map (Phase 7.5) ----
_SENIORITY_ALIASES = {
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


def _clean_text(value: Any) -> str | None:
    """Strip, collapse internal whitespace, return None for empty."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return _WHITESPACE_RUN.sub(" ", text)


def _clean_title(value: Any) -> str:
    """Titles must be non-empty strings."""
    cleaned = _clean_text(value)
    if not cleaned:
        raise ValueError("title is required and cannot be empty")
    return cleaned


def _clean_company(value: Any) -> str:
    """Company must be non-empty. Strip trailing punctuation."""
    cleaned = _clean_text(value)
    if not cleaned:
        raise ValueError("company is required and cannot be empty")
    cleaned = _TRAILING_PUNCT.sub("", cleaned).strip()
    if not cleaned:
        raise ValueError("company became empty after punctuation strip")
    return cleaned


def _clean_location(value: Any) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    cleaned = _TRAILING_PUNCT.sub("", cleaned).strip()
    return cleaned or None


def normalize_remote_status(value: Any) -> str:
    """Map free-form remote text to one of: remote, hybrid, onsite, unknown."""
    if value is None:
        return "unknown"
    key = str(value).strip().lower()
    return _REMOTE_ALIASES.get(key, "unknown")


def normalize_employment_type(value: Any) -> str:
    if value is None:
        return "unknown"
    return _EMPLOYMENT_TYPE_ALIASES.get(str(value).strip().lower(), "unknown")


def normalize_seniority(value: Any) -> str:
    if value is None:
        return "unknown"
    return _SENIORITY_ALIASES.get(str(value).strip().lower(), "unknown")


def normalize_country(value: Any) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


def normalize_description(value: Any) -> str:
    """Normalize line endings and trim excessive blank lines."""
    if value is None:
        return ""
    text = _CRLF.sub("\n", str(value))
    text = text.strip()
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text


def normalize_url(value: Any) -> str | None:
    """Trim whitespace; return None for empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_source(value: Any) -> str:
    """Lowercase source name. Defaults to 'manual'."""
    if value is None:
        return "manual"
    text = str(value).strip().lower()
    return text or "manual"


def normalize_external_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_salary(
    salary_min: Any,
    salary_max: Any,
    currency: Any,
) -> tuple[int | None, int | None, str | None]:
    """Validate and normalize salary fields."""
    def _to_int(v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            raise ValueError(f"salary must be an integer, got: {v!r}")

    lo = _to_int(salary_min)
    hi = _to_int(salary_max)
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"salary_min ({lo}) cannot exceed salary_max ({hi})")

    cur: str | None = None
    if currency is not None and str(currency).strip():
        cur = str(currency).strip().upper()
        if len(cur) != 3:
            raise ValueError(f"salary_currency must be a 3-letter code, got: {cur!r}")

    return lo, hi, cur


def normalize_datetime(value: Any) -> datetime | None:
    """Accept datetime or ISO string; return timezone-aware datetime or None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError(f"date_posted is not ISO-8601 parseable: {value!r}")
    else:
        raise ValueError(f"date_posted must be datetime or ISO string, got: {type(value)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_job_fields(payload: dict) -> dict:
    """
    Normalize every supported field in a raw job payload.

    Returns a new dict with normalized values. Missing optional fields
    are filled with sensible defaults. Raises ValueError on invalid input.
    """
    lo, hi, cur = normalize_salary(
        payload.get("salary_min"),
        payload.get("salary_max"),
        payload.get("salary_currency"),
    )

    return {
        "title": _clean_title(payload.get("title")),
        "company": _clean_company(payload.get("company")),
        "location": _clean_location(payload.get("location")),
        "country": normalize_country(payload.get("country")),
        "employment_type": normalize_employment_type(payload.get("employment_type")),
        "seniority": normalize_seniority(payload.get("seniority")),
        "remote_status": normalize_remote_status(payload.get("remote_status")),
        "description": normalize_description(payload.get("description")),
        "url": normalize_url(payload.get("url")),
        "source": normalize_source(payload.get("source")),
        "external_id": normalize_external_id(payload.get("external_id")),
        "date_posted": normalize_datetime(payload.get("date_posted")),
        "date_posted_status": payload.get("date_posted_status", "unknown"),
        "closing_date": normalize_datetime(payload.get("closing_date")),
        "closing_date_status": payload.get("closing_date_status", "unknown"),
        "availability_status": payload.get("availability_status", "unverified"),
        "date_last_verified": normalize_datetime(payload.get("date_last_verified")),
        "salary_min": lo,
        "salary_max": hi,
        "salary_currency": cur,
    }