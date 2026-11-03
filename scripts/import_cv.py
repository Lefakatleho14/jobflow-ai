"""
CLI: propose extracting a CV, then optionally apply it.

Usage:
    python scripts/import_cv.py path/to/cv.pdf              # dry-run, print proposal
    python scripts/import_cv.py path/to/cv.pdf --apply      # merge after confirmation
    python scripts/import_cv.py path/to/cv.pdf --apply --yes  # merge without prompt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import session_scope  # noqa: E402
from app.services.cv import (                     # noqa: E402
    CVError,
    CVImportService,
    CVProposal,
)


def _print_proposal(proposal: CVProposal) -> None:
    print("=" * 60)
    print(" JOBFLOW — CV PROPOSAL")
    print("=" * 60)
    print(f"  source    : {proposal.source_filename}")
    print(f"  stored as : {proposal.stored_filename or '(not stored)'}")
    print(f"  text len  : {len(proposal.raw_text)} chars")
    print()
    print(f"  SKILLS ({len(proposal.skills)})")
    print("-" * 60)
    if not proposal.skills:
        print("  (none detected)")
    else:
        for s in proposal.skills:
            print(f"  - {s.name:<16} [{s.category:<10}]  x{s.occurrences}")
            if s.evidence:
                print(f"      e.g. {s.evidence[:70]}")
    print()
    print(f"  EDUCATION ({len(proposal.education)})")
    print("-" * 60)
    if not proposal.education:
        print("  (none detected)")
    else:
        for e in proposal.education:
            print(f"  - {e.line}")
    print()
    print(f"  PROJECTS ({len(proposal.projects)})")
    print("-" * 60)
    if not proposal.projects:
        print("  (none detected)")
    else:
        for p in proposal.projects:
            print(f"  - {p.name}")
    print()
    if proposal.notes:
        print("  NOTES")
        print("-" * 60)
        for n in proposal.notes:
            print(f"  ! {n}")
        print()
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose extracting skills and projects from a CV")
    parser.add_argument("path", help="Path to a .pdf or .docx file")
    parser.add_argument("--apply", action="store_true", help="Apply the proposal to the profile")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt with --apply")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print(f"[FAIL] No such file: {path}")
        return 1

    try:
        with session_scope() as session:
            svc = CVImportService(session)
            proposal = svc.propose(path)
            _print_proposal(proposal)

            if not args.apply:
                print("Dry run. Re-run with --apply to merge into your profile.")
                return 0

            if not args.yes:
                print()
                answer = input("Apply this proposal to your profile? [y/N] ").strip().lower()
                if answer != "y":
                    print("[=] Cancelled.")
                    return 0

            summary = svc.apply(proposal, confirm=True)

            print("=" * 60)
            print(" APPLIED")
            print("=" * 60)
            print(f"  added skills    : {summary['added_skills']}")
            print(f"  updated skills  : {summary['updated_skills']}")
            print(f"  added projects  : {summary['added_projects']}")
            print(f"  education update: {'yes' if summary['education_updated'] else 'no'}")
            print("=" * 60)
        return 0
    except CVError as exc:
        print(f"[FAIL] {exc}")
        return 1
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())