"""
CLI: score jobs against the profile.

Usage:
    python scripts/score_jobs.py                 # score all unscored jobs
    python scripts/score_jobs.py --limit 5       # score 5 jobs
    python scripts/score_jobs.py --job <id>      # score one specific job
    python scripts/score_jobs.py --stats         # show scores summary
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
from app.models import Job, JobMatch, Profile         # noqa: E402
from app.services.matching import MatchingService     # noqa: E402


def _print_stats() -> None:
    with session_scope() as session:
        total_jobs = session.execute(select(func.count(Job.id))).scalar_one()
        with_req = session.execute(
            select(func.count(Job.id)).join(JobMatch, JobMatch.job_id == Job.id)
        ).scalar_one()
        total_matches = session.execute(select(func.count(JobMatch.id))).scalar_one()

    print("=" * 60)
    print(" JOBFLOW — MATCHING STATS")
    print("=" * 60)
    print(f"  total jobs         : {total_jobs}")
    print(f"  scored             : {total_matches}")
    print("=" * 60)


def _print_match(job, match) -> None:
    print(f"  [{match.tier.upper():6}] {match.score:5.1f}  {job.title[:60]}")
    if match.strong_matches:
        print(f"           strong: {', '.join(match.strong_matches[:5])}")
    if match.missing_skills:
        print(f"           missing: {', '.join(match.missing_skills[:5])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score jobs against profile")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--job", help="Score specific job ID")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        _print_stats()
        return 0

    with session_scope() as session:
        svc = MatchingService(session)

        if args.job:
            job = session.get(Job, args.job)
            if job is None:
                print(f"[FAIL] No such job: {args.job}")
                return 1
            profile = session.execute(select(Profile)).scalars().first()
            if profile is None:
                print("[FAIL] No profile — create one first")
                return 1
            match = svc.score_and_save(job, profile)
            session.commit()
            print(f"[OK ] {job.title}: {match.score} ({match.tier})")
            return 0

        n = svc.score_batch(limit=args.limit)
        print(f"[OK ] Scored {n} job(s)")

    # Print top matches.
    with session_scope() as session:
        stmt = (
            select(Job, JobMatch)
            .join(JobMatch, JobMatch.job_id == Job.id)
            .order_by(JobMatch.score.desc())
            .limit(10)
        )
        rows = session.execute(stmt).all()

    if rows:
        print()
        print("=" * 60)
        print(" TOP MATCHES")
        print("=" * 60)
        for job, match in rows:
            _print_match(job, match)
        print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())