"""Job services: normalization, hashing, dedupe, import, fetch, sources, fuzzy."""

from app.services.jobs.alias import (
    AliasDecision,
    alias_exists,
    find_fuzzy_match,
    record_alias,
)
from app.services.jobs.dedupe import find_existing
from app.services.jobs.fetch_service import (
    FeedFetchResult,
    FetchReport,
    fetch_all_feeds,
    fetch_one_feed,
)
from app.services.jobs.fuzzy import (
    combined_similarity,
    companies_match,
    location_similarity,
    title_similarity,
)
from app.services.jobs.hashing import content_hash
from app.services.jobs.import_service import ImportResult, JobImportService
from app.services.jobs.normalizer import normalize_job_fields

__all__ = [
    "AliasDecision",
    "FeedFetchResult",
    "FetchReport",
    "ImportResult",
    "JobImportService",
    "alias_exists",
    "combined_similarity",
    "companies_match",
    "content_hash",
    "fetch_all_feeds",
    "fetch_one_feed",
    "find_existing",
    "find_fuzzy_match",
    "location_similarity",
    "normalize_job_fields",
    "record_alias",
    "title_similarity",
]