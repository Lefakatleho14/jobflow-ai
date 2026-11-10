"""
Skill classification: Strong / Partial / Missing.

No AI. No fuzzy matching. Deterministic string comparison with a small
synonym map and a small implication graph.

The implication graph is deliberately conservative. It only includes
pairs that are widely accepted as equivalent or strictly implied:

    "FastAPI" implies "REST APIs" and "Python" (FastAPI is a Python
    framework that is inherently a REST API).

    "React" implies "JavaScript" (React is a JS library).

    "Spring Boot" implies "Java" and "REST APIs" (Spring Boot is a
    Java-based framework for building REST services).

Do not add implications you're not confident in. A wrong implication
corrupts the score more than a missing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# ---- Synonym map: canonical → list of alternates ----
SYNONYMS: dict[str, list[str]] = {
    "c#": ["csharp", "c sharp", "c-sharp"],
    "c++": ["cpp", "cplusplus"],
    "javascript": ["js", "es6", "ecmascript"],
    "typescript": ["ts"],
    "postgresql": ["postgres", "psql"],
    "kubernetes": ["k8s"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "node.js": ["nodejs", "node js", "node"],
    "next.js": ["nextjs"],
    ".net": ["dotnet", "dot net"],
    "asp.net core": ["asp.net", "aspnet", "aspnetcore"],
    "golang": ["go"],
    "amazon web services": ["aws"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure"],
    "sql": ["structured query language"],
    "rest": ["rest apis", "rest api", "restful"],
    "graphql": [],
}

# ---- Implication map: skill → list of skills it implies ----
IMPLIES: dict[str, list[str]] = {
    "fastapi": ["python", "rest"],
    "flask": ["python", "rest"],
    "django": ["python", "rest"],
    "spring boot": ["java", "rest"],
    "spring": ["java"],
    "react": ["javascript"],
    "vue": ["javascript"],
    "next.js": ["javascript"],
    "node.js": ["javascript"],
    "asp.net core": ["c#", ".net"],
    ".net": ["c#"],
    "postgresql": ["sql"],
    "mysql": ["sql"],
    "sqlite": ["sql"],
    "sql server": ["sql"],
    "docker": ["devops"],
    "kubernetes": ["devops", "docker"],
}


def _canonical(s: str) -> str:
    """Lowercase and strip whitespace."""
    return s.strip().lower()


def _expand_synonyms(name: str) -> set[str]:
    """Return all known surface forms for a skill, plus the name itself."""
    canon = _canonical(name)
    variants = {canon}
    for canonical, aliases in SYNONYMS.items():
        if canon == canonical:
            variants.update(_canonical(a) for a in aliases)
        elif canon in [_canonical(a) for a in aliases]:
            variants.add(canonical)
            variants.update(_canonical(a) for a in aliases)
    return variants


def _expand_implications(name: str) -> set[str]:
    """Return skills that `name` implies."""
    canon = _canonical(name)
    implied = set(IMPLIES.get(canon, []))
    # Add canonical aliases of implied skills too.
    out = set(implied)
    for imp in implied:
        out |= _expand_synonyms(imp)
    return out


@dataclass
class SkillMatch:
    """Result of classifying a single required skill."""
    required: str
    status: str                    # "strong" | "partial" | "missing"
    evidence: str | None = None    # what evidence (a skill name, or None)


def classify_skill(
    required: str,
    *,
    profile_skills: Iterable[str],
    profile_frameworks: Iterable[str],
    profile_languages: Iterable[str],
    profile_databases: Iterable[str],
    profile_cloud: Iterable[str],
    profile_devops: Iterable[str],
    profile_tools: Iterable[str],
) -> SkillMatch:
    """
    Classify one required skill against all profile evidence sources.

    Sources are queried in order. First hit wins:
        1. Exact match in any source → strong
        2. Synonym match in any source → partial
        3. Profile skill implies the required skill → partial
        4. No match → missing
    """
    required_canon = _canonical(required)
    if not required_canon:
        return SkillMatch(required=required, status="missing")

    # Combine all profile sources into one list, preserving source labels
    sources: list[tuple[str, str]] = []  # (label, value)
    for label, items in [
        ("skills", profile_skills),
        ("frameworks", profile_frameworks),
        ("languages", profile_languages),
        ("databases", profile_databases),
        ("cloud", profile_cloud),
        ("devops", profile_devops),
        ("tools", profile_tools),
    ]:
        for item in items:
            if item:
                sources.append((label, str(item)))

    # 1. Exact match (case-insensitive)
    for label, value in sources:
        if _canonical(value) == required_canon:
            return SkillMatch(
                required=required,
                status="strong",
                evidence=f"profile.{label}:{value}",
            )

    # 2. Synonym match
    required_variants = _expand_synonyms(required)
    for label, value in sources:
        value_canon = _canonical(value)
        if value_canon in required_variants:
            return SkillMatch(
                required=required,
                status="partial",
                evidence=f"profile.{label}:{value} (synonym)",
            )

    # 3. Implication match: profile skill implies the required skill
    for label, value in sources:
        implied = _expand_implications(value)
        if required_canon in implied:
            return SkillMatch(
                required=required,
                status="partial",
                evidence=f"profile.{label}:{value} (implies)",
            )

    # 4. No match
    return SkillMatch(required=required, status="missing")