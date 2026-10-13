"""
Phase 4 tests: RSS parsing, registry, fetch service, mocked HTTP.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models import FeedSource, Job
from app.services.jobs import fetch_all_feeds, fetch_one_feed
from app.services.jobs.sources import SourceError, get_source_class, known_source_types
from app.services.jobs.sources.rss import RSSSource


# ---------------------------------------------------------------- fixtures

@pytest.fixture()
def session_factory():
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_feed_"))
    db_file = tmp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                           expire_on_commit=False)
    yield Session
    engine.dispose()


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    try:
        yield s
    finally:
        if not s.is_active:
            s.rollback()
        s.close()


# ---- Minimal well-formed RSS fixtures ----

RSS_OK = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Demo Jobs</title>
    <link>https://example.com</link>
    <description>Feed</description>
    <item>
      <title>Junior Python Developer</title>
      <author>Acme Inc</author>
      <link>https://example.com/jobs/1</link>
      <guid>acme-1</guid>
      <description>Python, FastAPI</description>
      <pubDate>Mon, 01 Sep 2025 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Backend Engineer</title>
      <author>Beta Ltd</author>
      <link>https://example.com/jobs/2</link>
      <guid>beta-1</guid>
      <description>Node, Postgres</description>
    </item>
  </channel>
</rss>
"""

RSS_MALFORMED = b"<rss><channel><title>oops"

RSS_EMPTY = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>
"""


def _mock_response(content: bytes, status: int = 200) -> httpx.Response:
    """Build a real httpx.Response so feedparser gets real bytes."""
    return httpx.Response(status_code=status, content=content, request=httpx.Request("GET", "https://example.com/feed"))


# ---------------------------------------------------------------- registry

def test_registry_knows_rss():
    assert "rss" in known_source_types()
    cls = get_source_class("rss")
    assert cls is RSSSource


def test_registry_unknown_type_raises():
    with pytest.raises(SourceError):
        get_source_class("nope")


# ---------------------------------------------------------------- rss parsing

@patch("app.services.jobs.sources.rss.httpx.get")
def test_rss_source_parses_valid_feed(mock_get):
    mock_get.return_value = _mock_response(RSS_OK)
    source = RSSSource(url="https://example.com/feed", source_tag="demo")
    payloads = source.fetch()
    assert len(payloads) == 2
    first = payloads[0]
    assert first["title"] == "Junior Python Developer"
    assert first["company"] == "Acme Inc"
    assert first["url"] == "https://example.com/jobs/1"
    assert first["external_id"] == "acme-1"
    assert first["source"] == "demo"
    assert first["date_posted"] is not None


@patch("app.services.jobs.sources.rss.httpx.get")
def test_rss_source_raises_on_network_error(mock_get):
    mock_get.side_effect = httpx.ConnectError("boom")
    source = RSSSource(url="https://example.com/feed", source_tag="demo")
    with pytest.raises(SourceError):
        source.fetch()


@patch("app.services.jobs.sources.rss.httpx.get")
def test_rss_source_raises_on_http_error(mock_get):
    mock_get.return_value = _mock_response(b"nope", status=500)
    source = RSSSource(url="https://example.com/feed", source_tag="demo")
    with pytest.raises(SourceError):
        source.fetch()


@patch("app.services.jobs.sources.rss.httpx.get")
def test_rss_source_raises_on_malformed_feed(mock_get):
    mock_get.return_value = _mock_response(RSS_MALFORMED)
    source = RSSSource(url="https://example.com/feed", source_tag="demo")
    with pytest.raises(SourceError):
        source.fetch()


@patch("app.services.jobs.sources.rss.httpx.get")
def test_rss_source_returns_empty_for_empty_feed(mock_get):
    mock_get.return_value = _mock_response(RSS_EMPTY)
    source = RSSSource(url="https://example.com/feed", source_tag="demo")
    assert source.fetch() == []


# ---------------------------------------------------------------- fetch service

@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_one_feed_imports_entries(mock_get, session):
    mock_get.return_value = _mock_response(RSS_OK)
    feed = FeedSource(
        name="Demo",
        url="https://example.com/feed",
        source_type="rss",
        source_tag="demo",
    )
    session.add(feed)
    session.commit()

    result = fetch_one_feed(session, feed)
    session.commit()

    assert result.status == "ok"
    assert result.discovered == 2
    assert result.created == 2
    assert result.duplicates == 0
    assert session.query(Job).count() == 2


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_one_feed_marks_duplicates(mock_get, session):
    mock_get.return_value = _mock_response(RSS_OK)
    feed = FeedSource(
        name="Demo",
        url="https://example.com/feed",
        source_type="rss",
        source_tag="demo",
    )
    session.add(feed)
    session.commit()

    fetch_one_feed(session, feed)
    session.commit()
    # Same feed a second time → all duplicates
    result = fetch_one_feed(session, feed)
    session.commit()

    assert result.created == 0
    assert result.duplicates == 2
    assert session.query(Job).count() == 2


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_one_feed_records_error(mock_get, session):
    mock_get.side_effect = httpx.ConnectError("nope")
    feed = FeedSource(
        name="Broken",
        url="https://example.com/broken",
        source_type="rss",
        source_tag="demo",
    )
    session.add(feed)
    session.commit()

    result = fetch_one_feed(session, feed)
    session.commit()

    assert result.status == "error"
    assert feed.last_status == "error"
    assert feed.last_error is not None


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_one_feed_records_empty(mock_get, session):
    mock_get.return_value = _mock_response(RSS_EMPTY)
    feed = FeedSource(
        name="Empty",
        url="https://example.com/empty",
        source_type="rss",
        source_tag="demo",
    )
    session.add(feed)
    session.commit()

    result = fetch_one_feed(session, feed)
    session.commit()

    assert result.status == "empty"
    assert feed.last_status == "empty"
    assert feed.last_entry_count == 0


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_all_feeds_aggregates(mock_get, session):
    """Two distinct feeds produce distinct jobs."""
    RSS_B = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Data Engineer</title>
        <author>Gamma Co</author>
        <link>https://example.com/jobs/10</link>
        <guid>gamma-10</guid>
        <description>Spark, SQL</description>
      </item>
      <item>
        <title>DevOps Engineer</title>
        <author>Delta Co</author>
        <link>https://example.com/jobs/11</link>
        <guid>delta-11</guid>
        <description>Kubernetes, AWS</description>
      </item>
    </channel></rss>
    """

    def side_effect(url, **kwargs):
        if url.endswith("/a"):
            return _mock_response(RSS_OK)
        return _mock_response(RSS_B)

    mock_get.side_effect = side_effect

    session.add_all([
        FeedSource(name="A", url="https://example.com/a", source_type="rss", source_tag="a"),
        FeedSource(name="B", url="https://example.com/b", source_type="rss", source_tag="b"),
    ])
    session.commit()

    report = fetch_all_feeds(session)
    session.commit()

    assert report.feeds_processed == 2
    assert report.feeds_ok == 2
    assert report.discovered == 4
    assert report.created == 4
    assert report.duplicates == 0
    assert session.query(Job).count() == 4

@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_all_feeds_dedupes_across_feeds(mock_get, session):
    """The same job returned by two feeds is imported once."""
    mock_get.return_value = _mock_response(RSS_OK)

    session.add_all([
        FeedSource(name="A", url="https://example.com/a", source_type="rss", source_tag="a"),
        FeedSource(name="B", url="https://example.com/b", source_type="rss", source_tag="b"),
    ])
    session.commit()

    report = fetch_all_feeds(session)
    session.commit()

    assert report.feeds_processed == 2
    assert report.feeds_ok == 2
    assert report.discovered == 4        # both feeds returned 2 each
    assert report.created == 2           # A created them
    assert report.duplicates == 2        # B found them already
    assert session.query(Job).count() == 2


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_all_feeds_skips_disabled(mock_get, session):
    mock_get.return_value = _mock_response(RSS_OK)

    session.add_all([
        FeedSource(name="On",  url="https://example.com/on",  source_type="rss", source_tag="on",  enabled=True),
        FeedSource(name="Off", url="https://example.com/off", source_type="rss", source_tag="off", enabled=False),
    ])
    session.commit()

    report = fetch_all_feeds(session)
    session.commit()

    assert report.feeds_processed == 1
    assert session.query(Job).count() == 2


@patch("app.services.jobs.sources.rss.httpx.get")
def test_fetch_all_feeds_continues_after_error(mock_get, session):
    # First feed errors, second works. Order matters for the mock.
    mock_get.side_effect = [
        httpx.ConnectError("down"),
        _mock_response(RSS_OK),
    ]

    session.add_all([
        FeedSource(name="Bad",  url="https://example.com/bad",  source_type="rss", source_tag="bad"),
        FeedSource(name="Good", url="https://example.com/good", source_type="rss", source_tag="good"),
    ])
    session.commit()

    report = fetch_all_feeds(session)
    session.commit()

    assert report.feeds_processed == 2
    assert report.feeds_failed == 1
    assert report.feeds_ok == 1
    assert report.created == 2