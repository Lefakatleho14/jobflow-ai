"""
CLI for the migrations package.

Usage:
    python -m migrations            # apply pending migrations
    python -m migrations --status   # show applied + pending, don't apply
    python -m migrations --list     # same as --status (alias)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make project root importable when run as -m from any directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DATABASE_URL, engine  # noqa: E402
from migrations import run_migrations, status  # noqa: E402


def _print_status() -> None:
    s = status(engine)
    print("=" * 60)
    print(" JOBFLOW — MIGRATION STATUS")
    print("=" * 60)
    print(f"  url        : {DATABASE_URL}")
    print(f"  discovered : {len(s['discovered'])}")
    print(f"  applied    : {len(s['applied'])}")
    print(f"  pending    : {len(s['pending'])}")
    print("-" * 60)
    if s["applied"]:
        print("  APPLIED")
        for row in s["applied"]:
            print(f"    [OK ] {row['id']:<40} {row['duration_ms']:>5} ms")
    if s["pending"]:
        print("  PENDING")
        for mid in s["pending"]:
            print(f"    [   ] {mid}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="JobFlow AI migrations")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--list", action="store_true", help="Alias for --status")
    args = parser.parse_args()

    if args.status or args.list:
        _print_status()
        return 0

    applied_now = run_migrations(engine)
    if not applied_now:
        print("[=] No pending migrations. Database is up to date.")
        return 0

    print("=" * 60)
    print(" JOBFLOW — MIGRATIONS APPLIED")
    print("=" * 60)
    for mid in applied_now:
        print(f"  [OK ] {mid}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())