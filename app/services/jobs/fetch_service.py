"""
Fetch service.

Iterates enabled FeedSource rows, instantiates the right source class,
fetches payloads, and runs each payload through JobImportService.

One transaction per feed. Failures on a feed are recorded on that row
and do not abort the whole run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.models import FeedSource
from app.services.jobs.import_service import JobImportService
from app.services.jobs.sources import SourceError, get_source_class

logger = logging.getLogger(__name__)


@dataclass
class FeedFetchResult:
    feed_id: str
    feed_name: str
    feed_url: str
    status: str                    # "ok" | "error" | "empty"
    discovered: int = 0            # entries returned by the source
    created: int = 0               # newly inserted jobs
    duplicates: int = 0            # entries recognised as duplicates
    errors: int = 0                # per-entry import errors
    error_message: str | None = None


@dataclass
class FetchReport:
    feeds_processed: int = 0
    feeds_ok: int = 0
    feeds_failed: int = 0
    discovered: int = 0
    created: int = 0
    duplicates: int = 0
    errors: int = 0
    results: list[FeedFetchResult] = field(default_factory=list)


def fetch_one_feed(session: Session, feed: FeedSource) -> FeedFetchResult:
    """Fetch a single feed and import everything it returns. Does not commit."""
    result = FeedFetchResult(
        feed_id=feed.id,
        feed_name=feed.name,
        feed_url=feed.url,
        status="ok",
    )

    try:
        source_cls = get_source_class(feed.source_type)
        source = source_cls(url=feed.url, source_tag=feed.source_tag)
        payloads = source.fetch()
    except SourceError as exc:
        result.status = "error"
        result.error_message = str(exc)
        feed.last_status = "error"
        feed.last_error = str(exc)
        feed.last_fetched_at = utc_now()
        feed.last_entry_count = 0
        return result
    except Exception as exc:  # pragma: no cover — safety net
        result.status = "error"
        result.error_message = f"{type(exc).__name__}: {exc}"
        feed.last_status = "error"
        feed.last_error = result.error_message
        feed.last_fetched_at = utc_now()
        feed.last_entry_count = 0
        return result

    result.discovered = len(payloads)
    if not payloads:
        result.status = "empty"
        feed.last_status = "empty"
        feed.last_error = None
        feed.last_fetched_at = utc_now()
        feed.last_entry_count = 0
        return result

    service = JobImportService(session)
    for payload in payloads:
        try:
            import_result = service.import_job(payload)
            if import_result.created:
                result.created += 1
            else:
                result.duplicates += 1
        except Exception as exc:
            logger.warning("Import failed for one entry in feed %s: %s", feed.url, exc)
            result.errors += 1

    result.status = "ok"
    feed.last_status = "ok"
    feed.last_error = None
    feed.last_fetched_at = utc_now()
    feed.last_entry_count = result.discovered
    return result


def fetch_all_feeds(session: Session) -> FetchReport:
    """Iterate enabled feeds, fetch each, and aggregate a report. Does not commit."""
    report = FetchReport()
    stmt = select(FeedSource).where(FeedSource.enabled.is_(True)).order_by(FeedSource.name)
    feeds = list(session.execute(stmt).scalars().all())

    for feed in feeds:
        result = fetch_one_feed(session, feed)
        report.results.append(result)
        report.feeds_processed += 1
        report.discovered += result.discovered
        report.created += result.created
        report.duplicates += result.duplicates
        report.errors += result.errors
        if result.status == "error":
            report.feeds_failed += 1
        else:
            report.feeds_ok += 1

    return report