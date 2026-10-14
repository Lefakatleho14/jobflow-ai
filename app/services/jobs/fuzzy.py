"""
Fuzzy similarity helpers.

No external dependencies — uses difflib from the standard library plus
a small hand-written Levenshtein. Designed for short strings
(titles, locations) where speed and predictability matter more than
raw accuracy on prose.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# ---- Token canonicalization ----
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Common company suffix tokens — removed before comparison.
_COMPANY_SUFFIXES = {
    "inc", "incorporated",
    "ltd", "limited",
    "llc",
    "plc",
    "pty", "proprietary",
    "gmbh", "ag", "sa", "bv", "nv",
    "co", "company", "corp", "corporation",
    "holdings", "group",
}

# Common country/region tokens — removed from location comparisons.
_LOCATION_SUFFIXES = {
    "za", "rsa", "south africa",
    "us", "usa", "united states", "united states of america",
    "uk", "gb", "united kingdom", "england", "scotland", "wales",
    "ca", "canada", "au", "australia", "nz", "new zealand",
    "de", "germany", "fr", "france", "nl", "netherlands",
    "in", "india",
}

# Job-title abbreviations expanded before comparison.
# These are applied per-token; only whole tokens are replaced.
_TITLE_ABBREVIATIONS = {
    "jr": "junior",
    "sr": "senior",
    "dev": "developer",
    "eng": "engineer",
    "mgr": "manager",
    "swe": "software engineer",
    "sde": "software development engineer",
    "pm": "product manager",
    "qa": "quality assurance",
    "ui": "user interface",
    "ux": "user experience",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "bi": "business intelligence",
    "ds": "data science",
    "sre": "site reliability engineer",
    "ops": "operations",
    "admin": "administrator",
    "snr": "senior",
}


def canonical(text: str | None) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    s = text.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


def _expand_abbreviations(text: str) -> str:
    """Replace whole-token abbreviations with their full forms."""
    toks = text.split()
    expanded: list[str] = []
    for tok in toks:
        expanded.append(_TITLE_ABBREVIATIONS.get(tok, tok))
    return " ".join(expanded)


def canonical_title(text: str | None) -> str:
    """Canonical form for a job title — abbreviations expanded."""
    return _expand_abbreviations(canonical(text))


def tokens(text: str | None) -> set[str]:
    return set(canonical(text).split())


def tokens_title(text: str | None) -> set[str]:
    """Tokens for a title, with abbreviations expanded."""
    return set(canonical_title(text).split())


def strip_company_suffixes(text: str | None) -> str:
    """Remove common corporate suffixes like 'inc', 'ltd' from a company name."""
    toks = canonical(text).split()
    while toks and toks[-1] in _COMPANY_SUFFIXES:
        toks.pop()
    return " ".join(toks)


def strip_location_suffixes(text: str | None) -> str:
    """Remove trailing country/region tokens from a location."""
    toks = canonical(text).split()
    while toks:
        last = toks[-1]
        if last in _LOCATION_SUFFIXES:
            toks.pop()
            continue
        if len(toks) >= 2:
            two = f"{toks[-2]} {toks[-1]}"
            if two in _LOCATION_SUFFIXES:
                toks.pop()
                toks.pop()
                continue
        break
    return " ".join(toks)


def levenshtein(a: str, b: str) -> int:
    """Classic Levenshtein distance. O(len(a) * len(b))."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            )
        prev = curr
    return prev[-1]


def levenshtein_ratio(a: str, b: str) -> float:
    """1.0 for identical strings, 0.0 for maximally different. Length-aware."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = levenshtein(a, b)
    return 1.0 - (dist / max(len(a), len(b)))


def sequence_ratio(a: str, b: str) -> float:
    """difflib.SequenceMatcher ratio. Handles reorderings well."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def jaccard(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    return len(inter) / len(union)


def title_similarity(a: str | None, b: str | None) -> float:
    """
    Combined token + character similarity for job titles.

    Uses abbreviation-expanded canonical form. Weights favor sequence and
    edit-distance signals over raw token overlap, because abbreviations
    ('Jr.' vs 'Junior') and reorderings are common on job boards.
    """
    ca = canonical_title(a)
    cb = canonical_title(b)
    if not ca and not cb:
        return 1.0
    if not ca or not cb:
        return 0.0

    tok = jaccard(tokens_title(a), tokens_title(b))
    seq = sequence_ratio(ca, cb)
    lev = levenshtein_ratio(ca, cb)

    return 0.5 * seq + 0.3 * tok + 0.2 * lev


def location_similarity(a: str | None, b: str | None) -> float:
    """Location similarity after stripping country/region suffixes."""
    ca = strip_location_suffixes(a)
    cb = strip_location_suffixes(b)

    if not ca and not cb:
        return 1.0
    if not ca or not cb:
        return 0.5  # one side is empty — weak signal either way

    return jaccard(set(ca.split()), set(cb.split()))


def combined_similarity(
    *,
    title_a: str | None,
    title_b: str | None,
    location_a: str | None,
    location_b: str | None,
    title_weight: float = 0.75,
    location_weight: float = 0.25,
) -> tuple[float, float, float]:
    """
    Return (combined, title_sim, location_sim).

    Weights must sum to 1.0 (approximately). Raises ValueError if not.
    """
    if abs((title_weight + location_weight) - 1.0) > 1e-6:
        raise ValueError("Similarity weights must sum to 1.0")

    t = title_similarity(title_a, title_b)
    l = location_similarity(location_a, location_b)
    combined = title_weight * t + location_weight * l
    return combined, t, l


def companies_match(a: str | None, b: str | None) -> bool:
    """Two company names match if their suffix-stripped token sets overlap strongly."""
    ca = strip_company_suffixes(a)
    cb = strip_company_suffixes(b)
    if not ca or not cb:
        return False
    return jaccard(set(ca.split()), set(cb.split())) >= 0.6