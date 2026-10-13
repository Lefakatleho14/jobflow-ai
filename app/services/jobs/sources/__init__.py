"""Job sources: RSS and (later) other legal feed types."""

from app.services.jobs.sources.base import JobSource, RawJobPayload, SourceError
from app.services.jobs.sources.registry import (
    get_source_class,
    known_source_types,
    register_source,
)
from app.services.jobs.sources.rss import RSSSource

__all__ = [
    "JobSource",
    "RawJobPayload",
    "RSSSource",
    "SourceError",
    "get_source_class",
    "known_source_types",
    "register_source",
]