"""
Deterministic content hashing for job listings.

The hash captures (company, title, location) after normalization.
It is stable across runs, platforms, and Python versions.
"""

from __future__ import annotations

import hashlib

_HASH_LENGTH = 32


def content_hash(company: str, title: str, location: str | None) -> str:
    """
    Compute the canonical content hash for a job.

    Inputs are lowercased and stripped. None location becomes ''.
    """
    canonical = "|".join([
        (company or "").strip().lower(),
        (title or "").strip().lower(),
        (location or "").strip().lower(),
    ])
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_HASH_LENGTH]