"""
Registry mapping source_type strings to source classes.

This is what makes feed_sources.source_type DB-configurable.
"""

from __future__ import annotations

from typing import Callable, Type

from app.services.jobs.sources.base import JobSource, SourceError
from app.services.jobs.sources.rss import RSSSource

SourceFactory = Callable[..., JobSource]

_REGISTRY: dict[str, SourceFactory] = {
    "rss": RSSSource,
}


def get_source_class(source_type: str) -> Type[JobSource]:
    """Return the class registered for a source_type. Raises SourceError if unknown."""
    source_type = (source_type or "").strip().lower()
    cls = _REGISTRY.get(source_type)
    if cls is None:
        raise SourceError(f"Unknown source_type: {source_type!r}")
    return cls


def register_source(source_type: str, factory: SourceFactory) -> None:
    """Register a new source type. Useful for tests and future plugins."""
    _REGISTRY[source_type.strip().lower()] = factory


def known_source_types() -> list[str]:
    return sorted(_REGISTRY.keys())