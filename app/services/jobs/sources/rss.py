"""
RSS job source built on feedparser.

This source is deliberately conservative:
  * Sets a descriptive User-Agent.
  * Uses a per-request timeout.
  * Never raises per-entry; only whole-feed failures raise SourceError.
  * Does not follow links; it only trusts feed metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.services.jobs.sources.base import JobSource, RawJobPayload, SourceError

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "JobFlowAI/0.1 (+local personal job monitor)"
DEFAULT_TIMEOUT = 20.0
MAX_ENTRIES_PER_FETCH = 100


def _entry_to_payload(
    entry: Any,
    *,
    source_tag: str,
) -> RawJobPayload | None:
    """
    Convert a feedparser entry to a raw job payload.
    Returns None if the entry cannot produce a valid payload
    (e.g. missing title or company).
    """
    title = (entry.get("title") or "").strip()
    if not title:
        return None

    # Company is often in `author` on job boards; fall back to "Unknown"
    company = (
        entry.get("author")
        or entry.get("author_detail", {}).get("name") if isinstance(entry.get("author_detail"), dict) else None
    )
    company = (company or "Unknown").strip()

    # Location — some feeds include it in tags, some don't have it at all.
    location = None
    for tag in entry.get("tags", []) or []:
        term = (tag.get("term") or "").strip()
        if term and any(kw in term.lower() for kw in ("remote", "hybrid", "onsite", "on-site")):
            location = term
            break

    # Description — feedparser usually exposes `summary` or `description`
    description = entry.get("summary") or entry.get("description") or ""

    # URL — feed entries usually have a `link`
    url = entry.get("link") or None

    # External ID — use the feed's own id if present, else the link
    external_id = entry.get("id") or url

    # Date posted — parse common fields
    date_posted = None
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        struct = entry.get(field)
        if struct:
            try:
                date_posted = datetime(*struct[:6], tzinfo=timezone.utc)
                break
            except (TypeError, ValueError):
                continue

    return {
        "title": title,
        "company": company,
        "location": location,
        "remote_status": "unknown",  # RSS rarely has structured remote info
        "description": description,
        "url": url,
        "source": source_tag,
        "external_id": external_id,
        "date_posted": date_posted,
    }


class RSSSource(JobSource):
    """Fetch and parse an RSS/Atom feed into job payloads."""

    name = "rss"

    def __init__(
        self,
        url: str,
        *,
        source_tag: str,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_entries: int = MAX_ENTRIES_PER_FETCH,
    ) -> None:
        self.url = url
        self.source_tag = source_tag
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_entries = max_entries

    def fetch(self) -> list[RawJobPayload]:
        """Fetch the feed and return payloads. Raises SourceError on whole-feed failure."""
        try:
            response = httpx.get(
                self.url,
                headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
                timeout=self.timeout,
                follow_redirects=True,
            )
        except httpx.RequestError as exc:
            raise SourceError(f"HTTP error fetching {self.url}: {exc}") from exc

        if response.status_code >= 400:
            raise SourceError(f"HTTP {response.status_code} for {self.url}")

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            # Feed is malformed AND has no usable entries.
            raise SourceError(f"Malformed feed at {self.url}: {parsed.bozo_exception}")

        payloads: list[RawJobPayload] = []
        entries = list(parsed.entries)[: self.max_entries]
        for entry in entries:
            try:
                payload = _entry_to_payload(entry, source_tag=self.source_tag)
            except Exception as exc:  # pragma: no cover — safety net
                logger.warning("Skipping malformed entry in %s: %s", self.url, exc)
                continue
            if payload is not None:
                payloads.append(payload)

        logger.info("Fetched %d payload(s) from %s", len(payloads), self.url)
        return payloads