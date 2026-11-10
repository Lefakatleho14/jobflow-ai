"""
Deterministic matching scorer.

Given a Job (with JobRequirement) and the local Profile, compute a
transparent score from 0 to 100 across six weighted dimensions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobMatch, JobRequirement, Profile
from app.services.matching.skill_classifier import SkillMatch, classify_skill
from app.services.matching.weights import MatchingWeights, load_weights

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """Score for a single dimension, 0.0-1.0."""
    name: str
    sub_score: float
    weight: float
    detail: str = ""


@dataclass
class MatchResult:
    """Full result of scoring a job against a profile."""
    score: float                            # 0-100
    tier: str                               # "high" | "medium" | "low"
    dimensions: list[DimensionScore]
    strong_matches: list[str]
    partial_matches: list[str]
    missing_skills: list[str]
    explanation: str


def _collect_profile_skills(profile: Profile) -> dict[str, list[str]]:
    """Extract all profile skill sources as a dict for the classifier."""
    return {
        "profile_skills": [s.name for s in profile.skills],
        "profile_frameworks": list(profile.frameworks),
        "profile_languages": list(profile.languages),
        "profile_databases": list(profile.databases),
        "profile_cloud": list(profile.cloud),
        "profile_devops": list(profile.devops),
        "profile_tools": list(profile.tools),
    }


def _technical_dimension(
    job: Job,
    req: JobRequirement,
    profile_skills: dict,
) -> tuple[DimensionScore, list[str], list[str], list[str]]:
    """
    Compute the technical sub-score across all technical categories.
    Returns (dimension, strong, partial, missing) as lists of skill names.
    """
    required: list[str] = []
    for category in ("languages", "frameworks", "databases", "cloud", "devops"):
        for skill in getattr(req, category):
            if skill and skill.strip():
                required.append(skill.strip())

    if not required:
        return (
            DimensionScore(name="technical", sub_score=1.0, weight=0.0,
                           detail="no technical requirements"),
            [], [], [],
        )

    strong: list[str] = []
    partial: list[str] = []
    missing: list[str] = []

    for skill_name in required:
        result: SkillMatch = classify_skill(
            skill_name,
            **profile_skills,
        )
        if result.status == "strong":
            strong.append(skill_name)
        elif result.status == "partial":
            partial.append(skill_name)
        else:
            missing.append(skill_name)

    total = len(required)
    earned = len(strong) * 1.0 + len(partial) * 0.5
    sub_score = earned / total

    return (
        DimensionScore(
            name="technical",
            sub_score=sub_score,
            weight=0.0,
            detail=f"{len(strong)} strong, {len(partial)} partial, {len(missing)} missing of {total}",
        ),
        strong, partial, missing,
    )


def _extract_degree_level(text: str) -> int:
    """
    Return a numeric level for degree text: 0=unknown, 1=diploma,
    2=bachelor, 3=master, 4=phd.
    """
    t = (text or "").lower()
    if not t:
        return 0
    if "phd" in t or "doctorate" in t or "doctoral" in t:
        return 4
    if "msc" in t or "master" in t or "mba" in t or "meng" in t or "m.a." in t:
        return 3
    if "bsc" in t or "bachelor" in t or "beng" in t or "btech" in t or "b.com" in t or "ba" in t.split():
        return 2
    if "diploma" in t or "advanced diploma" in t:
        return 1
    return 0


def _extract_field_keywords(text: str) -> set[str]:
    """
    Return a set of broad field keywords detected in the text.

    We use broad categories: computing, engineering, science, business, arts.
    """
    t = (text or "").lower()
    fields: set[str] = set()
    if any(kw in t for kw in (
        "computer science", "computing", "software", "information technology",
        "information systems", "data science", "informatics",
    )):
        fields.add("computing")
    if any(kw in t for kw in (
        "engineering", "electrical", "mechanical", "civil", "chemical",
    )) and "software" not in t:
        fields.add("engineering")
    if any(kw in t for kw in ("physics", "chemistry", "biology", "mathematics", "math")):
        fields.add("science")
    if any(kw in t for kw in ("business", "commerce", "accounting", "finance", "economics")):
        fields.add("business")
    if any(kw in t for kw in ("arts", "humanities", "history", "literature")):
        fields.add("arts")
    return fields


def _education_dimension(job: Job, req: JobRequirement, profile: Profile) -> DimensionScore:
    """
    Education sub-score.

    Considers both field of study and degree level.

    Rules:
      * No requirement -> 1.0
      * No profile data -> 0.5 (neutral)
      * Field mismatch (e.g. Physics vs CS) -> 0.3
      * Level too low (BSc < MSc required) -> 0.5
      * Field + level match -> 1.0
      * Field unclear on either side -> 0.7 (lenient)
    """
    required = [e for e in req.education if e and e.strip()]
    if not required:
        return DimensionScore(name="education", sub_score=1.0, weight=0.0,
                              detail="no education requirement")

    profile_text = f"{profile.education or ''} {profile.degree or ''}".strip()
    if not profile_text:
        return DimensionScore(name="education", sub_score=0.5, weight=0.0,
                              detail="no education data in profile")

    required_text = " ".join(required)
    req_level = _extract_degree_level(required_text)
    prof_level = _extract_degree_level(profile_text)
    req_fields = _extract_field_keywords(required_text)
    prof_fields = _extract_field_keywords(profile_text)

    # Field check
    if req_fields and prof_fields:
        field_match = bool(req_fields & prof_fields)
    elif req_fields or prof_fields:
        # Only one side has a recognized field -> can't decide -> lenient.
        field_match = None
    else:
        # Neither side has a recognizable field -> lenient.
        field_match = None

    # Level check
    if req_level > 0 and prof_level > 0:
        level_ok = prof_level >= req_level
    else:
        level_ok = None

    # Decide.
    if field_match is False:
        return DimensionScore(
            name="education", sub_score=0.3, weight=0.0,
            detail=f"field mismatch ({sorted(prof_fields) or '?'} vs {sorted(req_fields)})",
        )

    if level_ok is False:
        return DimensionScore(
            name="education", sub_score=0.5, weight=0.0,
            detail=f"degree level too low (profile={prof_level}, required={req_level})",
        )

    if field_match is True and level_ok is True:
        return DimensionScore(name="education", sub_score=1.0, weight=0.0,
                              detail="education matched (field and level)")

    if field_match is True and level_ok is None:
        return DimensionScore(name="education", sub_score=0.9, weight=0.0,
                              detail="education field matched; level unclear")

    # Lenient fallback -> cannot determine
    return DimensionScore(name="education", sub_score=0.7, weight=0.0,
                          detail="education partially matched (field/level unclear)")


def _experience_dimension(req: JobRequirement, profile: Profile) -> DimensionScore:
    """Experience sub-score."""
    required_years = req.experience_years
    if required_years is None or required_years <= 0:
        return DimensionScore(name="experience", sub_score=1.0, weight=0.0,
                              detail="no experience requirement")

    profile_years = max(
        (s.years for s in profile.skills if s.years is not None),
        default=None,
    )
    if profile_years is None:
        return DimensionScore(name="experience", sub_score=0.5, weight=0.0,
                              detail=f"job needs {required_years}y, profile years unknown")

    if profile_years >= required_years:
        return DimensionScore(name="experience", sub_score=1.0, weight=0.0,
                              detail=f"job needs {required_years}y, profile has {profile_years}y")

    sub = profile_years / required_years
    return DimensionScore(name="experience", sub_score=sub, weight=0.0,
                          detail=f"job needs {required_years}y, profile has {profile_years}y")


def _projects_dimension(req: JobRequirement, profile: Profile) -> DimensionScore:
    """Projects sub-score."""
    required_tech = set()
    for category in ("languages", "frameworks", "databases", "cloud", "devops"):
        for skill in getattr(req, category):
            if skill:
                required_tech.add(skill.strip().lower())

    if not required_tech:
        return DimensionScore(name="projects", sub_score=1.0, weight=0.0,
                              detail="no technical requirements")

    if not profile.projects:
        return DimensionScore(name="projects", sub_score=0.0, weight=0.0,
                              detail="no projects in profile")

    overlap: set[str] = set()
    for project in profile.projects:
        for tech in project.technologies:
            tech_lower = tech.strip().lower()
            if tech_lower in required_tech:
                overlap.add(tech_lower)

    sub = min(1.0, len(overlap) / 3.0)
    return DimensionScore(name="projects", sub_score=sub, weight=0.0,
                          detail=f"{len(overlap)} matching technolog{'y' if len(overlap) == 1 else 'ies'}")


def _location_dimension(job: Job, profile: Profile) -> DimensionScore:
    """Location sub-score."""
    job_remote = (job.remote_status or "").lower()
    if job_remote == "remote":
        return DimensionScore(name="location", sub_score=1.0, weight=0.0,
                              detail="remote job")

    profile_prefs = [p.strip().lower() for p in profile.preferred_locations if p]
    job_loc = (job.location or "").lower()
    job_country = (job.country or "").lower()

    if not profile_prefs:
        return DimensionScore(name="location", sub_score=0.5, weight=0.0,
                              detail="no location preference")

    for pref in profile_prefs:
        if pref in job_loc or pref in job_country:
            return DimensionScore(name="location", sub_score=1.0, weight=0.0,
                                  detail=f"matches preferred location {pref!r}")

    return DimensionScore(name="location", sub_score=0.3, weight=0.0,
                          detail="location mismatch")


def _other_dimension(job: Job, req: JobRequirement, profile: Profile) -> DimensionScore:
    """Other sub-score: seniority + soft skills."""
    score = 0.0
    parts: list[str] = []

    job_sen = (job.seniority or req.seniority or "").lower()
    if job_sen and job_sen != "unknown":
        prof_sen = "unknown"
        if profile.skills:
            seniorities = [s.proficiency.lower() for s in profile.skills if s.proficiency]
            if "advanced" in seniorities or "expert" in seniorities:
                prof_sen = "senior"
            elif "intermediate" in seniorities:
                prof_sen = "mid"
            else:
                prof_sen = "junior"

        if prof_sen == job_sen or (
            prof_sen == "mid" and job_sen in ("mid", "junior")
        ):
            score += 0.5
            parts.append(f"seniority {job_sen} matches")
        else:
            parts.append(f"seniority {job_sen} vs profile {prof_sen}")

    if req.soft_skills:
        overlap_count = 0
        summary = (profile.experience_summary or "").lower()
        for soft in req.soft_skills:
            if soft and soft.lower() in summary:
                overlap_count += 1
        if overlap_count > 0:
            score += 0.5
            parts.append(f"{overlap_count} soft skill(s) in profile")

    if not parts:
        return DimensionScore(name="other", sub_score=1.0, weight=0.0,
                              detail="no other requirements")
    return DimensionScore(name="other", sub_score=score, weight=0.0,
                          detail="; ".join(parts))


def _build_explanation(
    score: float,
    tier: str,
    tech: DimensionScore,
    edu: DimensionScore,
    exp: DimensionScore,
    proj: DimensionScore,
    loc: DimensionScore,
    oth: DimensionScore,
    strong: list[str],
    partial: list[str],
    missing: list[str],
) -> str:
    """Build a single human-readable explanation string."""
    parts: list[str] = [f"Score {score}/100 ({tier} match)."]

    if strong:
        parts.append(f"Strong: {', '.join(strong[:5])}.")
    if partial:
        parts.append(f"Partial: {', '.join(partial[:5])}.")
    if missing:
        parts.append(f"Missing: {', '.join(missing[:5])}.")

    parts.append(tech.detail.capitalize() + ".")
    if edu.sub_score < 0.9:
        parts.append(edu.detail.capitalize() + ".")
    if exp.sub_score < 0.9:
        parts.append(exp.detail.capitalize() + ".")
    if loc.sub_score < 0.9:
        parts.append(loc.detail.capitalize() + ".")

    return " ".join(parts)


def score_job(
    job: Job,
    profile: Profile,
    *,
    weights: MatchingWeights | None = None,
) -> MatchResult:
    """
    Compute the match score for a single job against a profile.
    """
    weights = weights or load_weights()
    req = job.requirement

    if req is None:
        return MatchResult(
            score=50.0,
            tier="medium",
            dimensions=[],
            strong_matches=[],
            partial_matches=[],
            missing_skills=[],
            explanation="No requirements extracted yet — cannot score precisely.",
        )

    profile_skills = _collect_profile_skills(profile)

    tech_dim, strong, partial, missing = _technical_dimension(job, req, profile_skills)
    edu_dim = _education_dimension(job, req, profile)
    exp_dim = _experience_dimension(req, profile)
    proj_dim = _projects_dimension(req, profile)
    loc_dim = _location_dimension(job, profile)
    oth_dim = _other_dimension(job, req, profile)

    tech_dim.weight = weights.technical
    edu_dim.weight = weights.education
    exp_dim.weight = weights.experience
    proj_dim.weight = weights.projects
    loc_dim.weight = weights.location
    oth_dim.weight = weights.other

    raw = (
        weights.technical  * tech_dim.sub_score +
        weights.education  * edu_dim.sub_score +
        weights.experience * exp_dim.sub_score +
        weights.projects   * proj_dim.sub_score +
        weights.location   * loc_dim.sub_score +
        weights.other      * oth_dim.sub_score
    )
    score = round(raw * 100, 1)
    tier = weights.tier_for(score)

    explanation = _build_explanation(
        score, tier, tech_dim, edu_dim, exp_dim, proj_dim, loc_dim, oth_dim,
        strong, partial, missing,
    )

    return MatchResult(
        score=score,
        tier=tier,
        dimensions=[tech_dim, edu_dim, exp_dim, proj_dim, loc_dim, oth_dim],
        strong_matches=strong,
        partial_matches=partial,
        missing_skills=missing,
        explanation=explanation,
    )


# ---- Service layer ----

class MatchingService:
    """
    Orchestrates scoring a job or a batch of jobs against the profile.
    Persists results to job_matches.
    """

    def __init__(self, session: Session, weights: MatchingWeights | None = None):
        self.session = session
        self.weights = weights or load_weights()

    def score_and_save(self, job: Job, profile: Profile) -> JobMatch:
        """Score a job, save/replace its JobMatch row, return it."""
        result = score_job(job, profile, weights=self.weights)

        existing = job.match
        if existing is None:
            match = JobMatch(
                job_id=job.id,
                profile_id=profile.id,
            )
            self.session.add(match)
        else:
            match = existing

        match.score = result.score
        match.tier = result.tier
        match.technical_score = result.dimensions[0].sub_score if len(result.dimensions) > 0 else 0
        match.education_score = result.dimensions[1].sub_score if len(result.dimensions) > 1 else 0
        match.experience_score = result.dimensions[2].sub_score if len(result.dimensions) > 2 else 0
        match.projects_score = result.dimensions[3].sub_score if len(result.dimensions) > 3 else 0
        match.location_score = result.dimensions[4].sub_score if len(result.dimensions) > 4 else 0
        match.other_score = result.dimensions[5].sub_score if len(result.dimensions) > 5 else 0
        match.strong_matches = result.strong_matches
        match.partial_matches = result.partial_matches
        match.missing_skills = result.missing_skills
        match.explanation = result.explanation
        match.matched_at = datetime.now(timezone.utc)

        self.session.flush()
        return match

    def score_batch(self, *, limit: int | None = None) -> int:
        """
        Score all jobs that have requirements and haven't been scored yet.
        Returns the number of jobs scored.
        """
        profile = self.session.execute(select(Profile)).scalars().first()
        if profile is None:
            raise RuntimeError("No profile found — create one first")

        stmt = (
            select(Job)
            .join(JobRequirement, JobRequirement.job_id == Job.id)
            .outerjoin(JobMatch, JobMatch.job_id == Job.id)
            .where(JobMatch.id.is_(None))
            .order_by(Job.date_found.asc().nullsfirst())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        jobs = list(self.session.execute(stmt).scalars().all())
        for job in jobs:
            self.score_and_save(job, profile)
            self.session.commit()
        return len(jobs)