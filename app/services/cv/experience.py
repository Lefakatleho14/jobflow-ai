"""
Heuristic extraction of education and project hints.

This is intentionally conservative: it finds obvious patterns and stops.
Better to surface 3 confident items than 20 noisy ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lines containing one of these indicate education.
_DEGREE_PATTERNS = [
    re.compile(
        r"\b(bachelor|bsc|ba|beng|btech|bcom|master|msc|ma|meng|mba|phd|doctorate)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcomputer science\b", re.IGNORECASE),
    re.compile(r"\binformation technology\b", re.IGNORECASE),
    re.compile(r"\bsoftware engineering\b", re.IGNORECASE),
]

# Project section headers, if the CV uses one.
_PROJECT_HEADER = re.compile(
    r"^\s*(projects?|personal projects?|selected projects?|portfolio)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ExtractedEducation:
    line: str


@dataclass
class ExtractedProjectName:
    name: str
    line: str


def extract_education(text: str) -> list[ExtractedEducation]:
    """
    Return lines that plausibly describe education. Deduplicated.
    """
    seen: set[str] = set()
    results: list[ExtractedEducation] = []
    for raw in text.split("\n"):
        line = " ".join(raw.split())
        if not line:
            continue
        if any(p.search(line) for p in _DEGREE_PATTERNS):
            key = line.lower()
            if key not in seen:
                seen.add(key)
                results.append(ExtractedEducation(line=line))
    return results


def extract_project_names(text: str) -> list[ExtractedProjectName]:
    """
    Return project names found under a 'Projects' header, if present.

    Heuristic: after a Projects header, each non-empty line that isn't
    indented too far and is relatively short is treated as a project name.
    """
    lines = text.split("\n")
    results: list[ExtractedProjectName] = []
    seen: set[str] = set()

    i = 0
    while i < len(lines):
        if _PROJECT_HEADER.match(lines[i]):
            i += 1
            # Collect until next blank-heavy boundary or next ALL-CAPS header.
            while i < len(lines):
                line = " ".join(lines[i].split())
                if not line:
                    i += 1
                    continue
                # Stop if this line looks like a new section header.
                if line.isupper() and len(line) > 3:
                    break
                # Only accept short-ish lines as project names.
                if len(line) <= 120 and not line.endswith("."):
                    key = line.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append(ExtractedProjectName(name=line, line=line))
                i += 1
            continue
        i += 1

    return results