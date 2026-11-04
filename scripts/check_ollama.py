"""
CLI: verify Ollama connectivity and model availability.

Usage:
    python scripts/check_ollama.py            # full check
    python scripts/check_ollama.py --health   # health only
    python scripts/check_ollama.py --ping     # health + live ping
    python scripts/check_ollama.py --extract "Some job description..."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv                     # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")                 # noqa: E402

from app.ai import LLMError, LLMService  # noqa: E402


def _print_health(status) -> None:
    print("=" * 60)
    print(" JOBFLOW — OLLAMA HEALTH")
    print("=" * 60)
    print(f"  available        : {status.available}")
    print(f"  base_url         : {status.base_url}")
    print(f"  configured_model : {status.model}")
    print(f"  models_available : {status.models_available}")
    print(f"  message          : {status.message}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Ollama connectivity")
    parser.add_argument("--health", action="store_true", help="Health check only")
    parser.add_argument("--ping", action="store_true", help="Health + live ping")
    parser.add_argument("--extract", metavar="TEXT",
                        help="Try requirement extraction on a sample text")
    args = parser.parse_args()

    svc = LLMService()

    status = svc.health()
    _print_health(status)

    if args.health:
        return 0 if status.available else 1

    if not status.available:
        print("[FAIL] Ollama is not ready. Fix the message above first.")
        return 1

    if args.ping or not args.extract:
        print("Pinging model with minimal prompt...")
        try:
            response = svc.ping()
            print(f"[OK ] Response: {response[:100]!r}")
        except LLMError as exc:
            print(f"[FAIL] {type(exc).__name__}: {exc}")
            return 1

    if args.extract:
        print()
        print("=" * 60)
        print(" EXTRACTION TEST")
        print("=" * 60)
        print(f"Input: {args.extract[:200]}")
        try:
            data = svc.extract_job_requirements(args.extract)
            print(f"[OK ] Response keys: {list(data.keys())}")
            print(json.dumps(data, indent=2)[:1500])
        except LLMError as exc:
            print(f"[FAIL] {type(exc).__name__}: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())