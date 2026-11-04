"""
CLI: extract structured requirements from stored jobs.

Usage:
    python scripts/analyse_jobs.py                  # process MAX_JOBS_PER_RUN jobs
    python scripts/analyse_jobs.py --limit 5        # process 5 jobs
    python scripts/analyse_jobs.py --job <id>       # specific job
    python scripts/analyse_jobs.py --all            # process all pending jobs
    python scripts/analyse_jobs.py --stats          # show extraction stats only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv                        # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")                    # noqa: E402

from sqlalchemy import func, select                   # noqa: E402

from app.database.connection import session_scope     # noqa: E402
from app.models import Job, JobRequirement            # noqa: E402
from app.services.jobs import RequirementService      # noqa: E402


def _print_stats() -> None:
    with session_scope() as session:
        total = session.execute(select(func.count(Job.id))).scalar_one()
        extracted = session.execute(
            select(func.count(JobRequirement.id))
        ).scalar_one()
        pending = total - extracted

    print("=" * 60)
    print(" JOBFLOW — REQUIREMENT EXTRACTION STATS")
    print("=" * 60)
    print(f"  total jobs         : {total}")
    print(f"  with requirements  : {extracted}")
    print(f"  pending extraction : {pending}")
    print("=" * 60)


def _print_report(report) -> None:
    print("=" * 60)
    print(" JOBFLOW — EXTRACTION REPORT")
    print("=" * 60)
    print(f"  candidates : {report.total_candidates}")
    print(f"  extracted  : {report.extracted}")
    print(f"  skipped    : {report.skipped}")
    print(f"  failed     : {report.failed}")
    print("-" * 60)
    for r in report.results:
        marker = "OK " if r.status == "extracted" else ("SKIP" if r.status == "skipped" else "FAIL")
        print(f"  [{marker}] {r.job_title[:60]}")
        if r.status != "extracted" and r.reason:
            print(f"         {r.reason}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract requirements from jobs")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--job", help="Extract from a specific job ID")
    parser.add_argument("--all", action="store_true", help="Process all pending jobs")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    args = parser.parse_args()

    if args.stats:
        _print_stats()
        return 0

    # Determine batch size.
    if args.all:
        limit = None
    elif args.limit is not None:
        limit = args.limit
    else:
        limit = 10  # default; extract_batch honors MAX_JOBS_PER_RUN if limit None

    job_ids = [args.job] if args.job else None

    with session_scope() as session:
        svc = RequirementService(session)
        report = svc.extract_batch(limit=limit, job_ids=job_ids)
        _print_report(report)

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())