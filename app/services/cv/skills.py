"""
Deterministic skill extraction from CV text.

We match against a curated vocabulary of common languages, frameworks,
databases, cloud platforms, and tools. This is keyword matching, not AI.

The vocabulary can be extended by editing `VOCABULARY` below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Each entry: (canonical_name, category, list of match patterns)
# Patterns are matched case-insensitively as whole words.
VOCABULARY: list[tuple[str, str, list[str]]] = [
    # Languages
    ("Python", "language", ["python"]),
    ("Java", "language", ["java"]),
    ("JavaScript", "language", ["javascript", "js"]),
    ("TypeScript", "language", ["typescript"]),
    ("C#", "language", ["c#", "csharp", "c sharp"]),
    ("C++", "language", ["c++", "cpp"]),
    ("C", "language", [" c "]),
    ("Go", "language", ["golang", " go "]),
    ("Rust", "language", ["rust"]),
    ("Ruby", "language", ["ruby"]),
    ("PHP", "language", ["php"]),
    ("Swift", "language", ["swift"]),
    ("Kotlin", "language", ["kotlin"]),
    ("Scala", "language", ["scala"]),
    ("R", "language", ["r programming", " r "]),
    ("SQL", "language", ["sql"]),

    # Frameworks
    ("FastAPI", "framework", ["fastapi", "fast api"]),
    ("Flask", "framework", ["flask"]),
    ("Django", "framework", ["django"]),
    ("Spring Boot", "framework", ["spring boot", "springboot"]),
    ("Spring", "framework", ["spring framework", "spring mvc"]),
    ("React", "framework", ["react", "reactjs", "react.js"]),
    ("Vue", "framework", ["vue", "vuejs", "vue.js"]),
    ("Angular", "framework", ["angular", "angularjs"]),
    ("Node.js", "framework", ["node.js", "nodejs", "node js"]),
    ("Express", "framework", ["express.js", "expressjs", "express"]),
    ("Next.js", "framework", ["next.js", "nextjs"]),
    (".NET", "framework", [".net", "dotnet", "asp.net"]),
    ("ASP.NET Core", "framework", ["asp.net core", "aspnet core"]),

    # Databases
    ("SQLite", "database", ["sqlite", "sqlite3"]),
    ("PostgreSQL", "database", ["postgresql", "postgres"]),
    ("MySQL", "database", ["mysql"]),
    ("MongoDB", "database", ["mongodb", "mongo"]),
    ("Redis", "database", ["redis"]),
    ("Oracle", "database", ["oracle db", "oracle database"]),
    ("SQL Server", "database", ["sql server", "mssql"]),

    # Cloud
    ("AWS", "cloud", ["aws", "amazon web services"]),
    ("Azure", "cloud", ["azure", "microsoft azure"]),
    ("GCP", "cloud", ["gcp", "google cloud", "google cloud platform"]),

    # DevOps
    ("Docker", "devops", ["docker"]),
    ("Kubernetes", "devops", ["kubernetes", "k8s"]),
    ("Terraform", "devops", ["terraform"]),
    ("Ansible", "devops", ["ansible"]),
    ("Jenkins", "devops", ["jenkins"]),
    ("GitHub Actions", "devops", ["github actions"]),
    ("GitLab CI", "devops", ["gitlab ci", "gitlab-ci"]),
    ("CircleCI", "devops", ["circleci", "circle ci"]),

    # Tools
    ("Git", "tool", ["git", "github", "gitlab", "bitbucket"]),
    ("Linux", "tool", ["linux", "ubuntu", "debian"]),
    ("Bash", "tool", ["bash", "shell scripting"]),
    ("Postman", "tool", ["postman"]),
    ("Jira", "tool", ["jira"]),
    ("Figma", "tool", ["figma"]),
    ("Pytest", "tool", ["pytest"]),
    ("Selenium", "tool", ["selenium"]),
]


@dataclass
class ExtractedSkill:
    name: str
    category: str
    evidence: str | None = None    # the surrounding text snippet
    occurrences: int = 0


def _build_pattern(pattern: str) -> re.Pattern[str]:
    """
    Build a whole-word pattern for a skill keyword.

    We pad with word boundaries except when the pattern starts/ends with
    a non-word char (e.g. 'c#', 'c++', '.net'). In those cases we manually
    construct the boundary so '#', '+', and '.' are handled correctly.
    """
    p = pattern.strip()
    if not p:
        return re.compile(r"$^")  # never matches

    # If pattern already has whitespace padding, strip it for boundary logic.
    left = r"(?<!\w)"
    right = r"(?!\w)"
    return re.compile(left + re.escape(p) + right, re.IGNORECASE)


_PATTERNS = [
    (name, category, [_build_pattern(p) for p in patterns])
    for name, category, patterns in VOCABULARY
]


def _snippet(text: str, start: int, end: int, window: int = 40) -> str:
    a = max(0, start - window)
    b = min(len(text), end + window)
    return " ".join(text[a:b].split())


def extract_skills(text: str) -> list[ExtractedSkill]:
    """
    Return skills found in `text`. Deduplicates by canonical name.
    """
    results: dict[str, ExtractedSkill] = {}
    for name, category, patterns in _PATTERNS:
        total = 0
        first_snippet: str | None = None
        for pat in patterns:
            for match in pat.finditer(text):
                total += 1
                if first_snippet is None:
                    first_snippet = _snippet(text, match.start(), match.end())
        if total > 0:
            results[name] = ExtractedSkill(
                name=name,
                category=category,
                evidence=first_snippet,
                occurrences=total,
            )
    return sorted(results.values(), key=lambda s: s.name)