"""
CLI: import a single job from a JSON payload.

Usage:
    python scripts/import_job.py path/to/job.json
    python scripts/import_job.py --inline '{"title": "...", "company": "..."}'

Exit codes:
    0  success (created or duplicate found — both are OK)
    1  validation error
    2  other error (DB, IO, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import session_scope  # noqa: E402
from app.services.jobs import JobImportService     # noqa: E402


def _load_payload(args: argparse.Namespace) -> dict:
    if args.path:
        p = Path(args.path)
        if not p.is_file():
            raise FileNotFoundError(f"No such file: {p}")
        return json.loads(p.read_text(encoding="utf-8"))
    if args.inline:
        return json.loads(args.inline)
    raise ValueError("Provide either a JSON file path or --inline JSON")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a single job into JobFlow AI")
    parser.add_argument("path", nargs="?", help="Path to a JSON file")
    parser.add_argument("--inline", help="Raw JSON string")
    args = parser.parse_args()

    try:
        payload = _load_payload(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    try:
        with session_scope() as session:
            result = JobImportService(session).import_job(payload)
            job = result.job
            status = "CREATED" if result.created else "DUPLICATE"
            print("=" * 56)
            print(f" {status}")
            print("=" * 56)
            print(f"  id        : {job.id}")
            print(f"  title     : {job.title}")
            print(f"  company   : {job.company}")
            print(f"  location  : {job.location}")
            print(f"  source    : {job.source}")
            print(f"  hash      : {job.content_hash}")
            print(f"  status    : {job.status}")
        return 0
    except ValueError as exc:
        print(f"[FAIL] Validation error: {exc}")
        return 1
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())