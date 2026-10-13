"""
CLI: run a fetch cycle over all enabled feeds.

Usage:
    python scripts/fetch_feeds.py
    python scripts/fetch_feeds.py --feed <feed_id>
    python scripts/fetch_feeds.py --seed-demo   (add the two seed feeds if missing)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database.connection import session_scope  # noqa: E402
from app.models import FeedSource  # noqa: E402
from app.services.jobs import fetch_all_feeds, fetch_one_feed  # noqa: E402


# Two well-known, legal RSS feeds for demonstration.
DEMO_FEEDS = [
    {
        "name": "WeWorkRemotely — Remote Programming Jobs",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "source_type": "rss",
        "source_tag": "weworkremotely",
    },
    {
        "name": "Python.org Job Board",
        "url": "https://www.python.org/jobs/feed/rss/",
        "source_type": "rss",
        "source_tag": "pythonorg",
    },
]


def _seed_demo_feeds() -> None:
    """Add the demo feeds if they don't already exist (matched by URL)."""
    with session_scope() as session:
        for spec in DEMO_FEEDS:
            exists = session.execute(
                select(FeedSource).where(FeedSource.url == spec["url"])
            ).scalar_one_or_none()
            if exists is None:
                session.add(FeedSource(**spec))
                print(f"[+] Added feed: {spec['name']}")
            else:
                print(f"[=] Feed already present: {spec['name']}")


def _print_report(report) -> None:
    print("=" * 60)
    print(" JOBFLOW — FEED FETCH REPORT")
    print("=" * 60)
    print(f"  feeds_processed : {report.feeds_processed}")
    print(f"  feeds_ok        : {report.feeds_ok}")
    print(f"  feeds_failed    : {report.feeds_failed}")
    print(f"  discovered      : {report.discovered}")
    print(f"  created         : {report.created}")
    print(f"  duplicates      : {report.duplicates}")
    print(f"  errors          : {report.errors}")
    print("-" * 60)
    for r in report.results:
        marker = "OK " if r.status == "ok" else ("EMP" if r.status == "empty" else "ERR")
        print(f"  [{marker}] {r.feed_name}")
        print(f"         url     : {r.feed_url}")
        print(f"         found   : {r.discovered}  created: {r.created}  dup: {r.duplicates}  err: {r.errors}")
        if r.error_message:
            print(f"         error   : {r.error_message}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch jobs from enabled feeds")
    parser.add_argument("--feed", help="Fetch only a specific feed id")
    parser.add_argument("--seed-demo", action="store_true", help="Add demo feeds if missing, then exit")
    args = parser.parse_args()

    if args.seed_demo:
        _seed_demo_feeds()
        return 0

    if args.feed:
        with session_scope() as session:
            feed = session.get(FeedSource, args.feed)
            if feed is None:
                print(f"[FAIL] No such feed: {args.feed}")
                return 1
            result = fetch_one_feed(session, feed)

        # Wrap the single result to reuse report printer
        class _R:
            pass
        report = _R()
        report.feeds_processed = 1
        report.feeds_ok = 1 if result.status != "error" else 0
        report.feeds_failed = 1 if result.status == "error" else 0
        report.discovered = result.discovered
        report.created = result.created
        report.duplicates = result.duplicates
        report.errors = result.errors
        report.results = [result]
        _print_report(report)
        return 0

    with session_scope() as session:
        report = fetch_all_feeds(session)
        # `session_scope` commits after the block; because fetch_all_feeds
        # only flushes, the final commit here persists everything at once.
        # For per-feed commit granularity, see fetch_one_feed + loop.

    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())