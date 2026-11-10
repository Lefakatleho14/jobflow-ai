"""
Matching weights configuration.

Reads from .env at load time (via process entry point). All weights
must sum to 1.0. Loaded once and reused for all scoring operations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "")
    if not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, "")
    if not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class MatchingWeights:
    """
    Configurable dimension weights. All weights must sum to 1.0.
    """
    technical: float = 0.40
    education: float = 0.20
    experience: float = 0.15
    projects: float = 0.10
    location: float = 0.10
    other: float = 0.05

    def validate(self) -> None:
        total = (
            self.technical + self.education + self.experience
            + self.projects + self.location + self.other
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Matching weights must sum to 1.0, got {total}")

    @property
    def high_threshold(self) -> float:
        return _env_float("MATCH_THRESHOLD_HIGH", 85.0)

    @property
    def medium_threshold(self) -> float:
        return _env_float("MATCH_THRESHOLD_MEDIUM", 70.0)

    def tier_for(self, score: float) -> str:
        if score >= self.high_threshold:
            return "high"
        if score >= self.medium_threshold:
            return "medium"
        return "low"


def load_weights() -> MatchingWeights:
    """Load weights from env with defaults, then validate."""
    w = MatchingWeights(
        technical=_env_float("MATCH_WEIGHT_TECHNICAL", 0.40),
        education=_env_float("MATCH_WEIGHT_EDUCATION", 0.20),
        experience=_env_float("MATCH_WEIGHT_EXPERIENCE", 0.15),
        projects=_env_float("MATCH_WEIGHT_PROJECTS", 0.10),
        location=_env_float("MATCH_WEIGHT_LOCATION", 0.10),
        other=_env_float("MATCH_WEIGHT_OTHER", 0.05),
    )
    w.validate()
    return w