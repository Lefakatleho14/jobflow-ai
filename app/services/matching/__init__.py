"""Matching services: deterministic scoring and skill classification."""

from app.services.matching.scorer import (
    DimensionScore,
    MatchResult,
    MatchingService,
    score_job,
)
from app.services.matching.skill_classifier import SkillMatch, classify_skill
from app.services.matching.weights import MatchingWeights, load_weights

__all__ = [
    "DimensionScore",
    "MatchResult",
    "MatchingService",
    "MatchingWeights",
    "SkillMatch",
    "classify_skill",
    "load_weights",
    "score_job",
]