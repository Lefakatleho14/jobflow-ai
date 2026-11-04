"""
CLI: natural-language job search.

Usage:
    python scripts/search_jobs.py "junior python developer remote johannesburg"
    python scripts/search_jobs.py "senior backend in Cape Town last 7 days"
    python scripts/search_jobs.py --show-filters "graduate dev role"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import session_scope          # noqa: E402
from app.services.search import build_query, parse_query  # noqa: E402


def _print_filters(filters) -> None:
    print("=" * 60)
    print(" JOBFLOW — SEARCH FILTERS")
    print("=" * 60)
    print(f"  query            : {filters.raw_query!r}")
    print(f"  titles           : {filters.titles}")
    print(f"  seniority        : {filters.seniority}")
    print(f"  employment_types : {filters.employment_types}")
    print(f"  remote_pref      : {filters.remote_preference}")
    print(f"  locations        : {filters.locations}")
    print(f"  countries        : {filters.countries}")
    print(f"  required_skills  : {filters.required_skills}")
    print(f"  within_days      : {filters.date_posted_within_days}")
    print("=" * 60)


def _print_results(jobs) -> None:
    print()
    print(f"RESULTS: {len(jobs)} job(s)")
    print("-" * 60)
    if not jobs:
        print("  (no matches)")
        return
    for job in jobs:
        title = (job.title or "")[:60]
        print(f"  {title}")
        loc = job.location or "—"
        country = job.country or "—"
        print(f"      {job.company}  |  {loc}  |  {country}  |  source={job.source}")
        if job.seniority and job.seniority != "unknown":
            print(f"      seniority={job.seniority}  employment={job.employment_type or '?'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Natural-language job search")
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument("--show-filters", action="store_true",
                        help="Print parsed filters (always on unless suppressed)")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    args = parser.parse_args()

    filters = parse_query(args.query)
    _print_filters(filters)

    if filters.is_empty():
        print("No recognizable filters — try including a title, skill, or location.")
        return 1

    with session_scope() as session:
        stmt = build_query(filters, limit=args.limit)
        jobs = list(session.execute(stmt).scalars().all())

    _print_results(jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())