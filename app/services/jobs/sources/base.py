"""
Job source interface.

Every source class returns a list of raw payload dicts that are shaped
exactly like what `normalize_job_fields` consumes. This keeps the source
layer decoupled from the import layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

RawJobPayload = dict[str, Any]


class SourceError(Exception):
    """Raised when a source cannot complete a fetch (whole-feed failure)."""


class JobSource(ABC):
    """
    Base class for all job sources.

    Subclasses must:
      * set a unique `name` (matches FeedSource.source_type)
      * implement `fetch()` returning a list of raw payloads
    """

    name: str = "abstract"

    @abstractmethod
    def fetch(self) -> list[RawJobPayload]:
        """Return candidate job payloads.

        Must NOT raise for individual entry problems — log and skip.
        May raise `SourceError` for whole-feed failures (network, parse).
        """