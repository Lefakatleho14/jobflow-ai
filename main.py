"""
JobFlow AI — sanity-check entrypoint.

This file will NOT contain the real application.
Its only job in Phase 1 is to prove:
  1. The virtual environment works.
  2. Dependencies import correctly.
  3. The project package structure resolves.
  4. The .env file is readable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    # ---- Load environment ----
    root = Path(__file__).resolve().parent
    env_path = root / ".env"
    if not env_path.exists():
        print(f"[FAIL] .env not found at {env_path}")
        print("       Copy .env.example to .env first.")
        return 1

    load_dotenv(env_path)

    print("=" * 56)
    print(" JobFlow AI — Phase 1 sanity check")
    print("=" * 56)

    # ---- Python version ----
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[OK]   Python version         : {py}")

    # ---- Project root ----
    print(f"[OK]   Project root           : {root}")

    # ---- Key environment variables ----
    for key in (
        "OLLAMA_BASE_URL",
        "EMBEDDING_MODEL",
        "DATABASE_PATH",
        "MATCH_THRESHOLD_HIGH",
        "MATCH_THRESHOLD_MEDIUM",
        "MAX_JOBS_PER_RUN",
    ):
        value = os.getenv(key, "<unset>")
        print(f"[OK]   {key:<24}: {value}")

    # ---- Import check ----
    try:
        import fastapi            # noqa: F401
        import pydantic           # noqa: F401
        import sqlalchemy         # noqa: F401
        import ollama             # noqa: F401
        import apscheduler        # noqa: F401
        import streamlit          # noqa: F401
        import pandas             # noqa: F401
        import feedparser         # noqa: F401
        import httpx              # noqa: F401
        print("[OK]   Core dependencies     : importable")
    except ImportError as exc:
        print(f"[FAIL] Missing dependency: {exc.name}")
        print("       Run: pip install -r requirements.txt")
        return 1

    # ---- Note: sentence-transformers is heavy; report but don't fail ----
    try:
        import sentence_transformers  # noqa: F401
        print("[OK]   sentence-transformers: importable")
    except ImportError:
        print("[WARN] sentence-transformers not importable (install before Phase 11)")

    # ---- Package structure ----
    try:
        import app                    # noqa: F401
        import app.services.jobs      # noqa: F401
        import app.services.matching  # noqa: F401
        import app.services.cv        # noqa: F401
        import app.services.notifications  # noqa: F401
        import app.automation         # noqa: F401
        import app.utils              # noqa: F401
        print("[OK]   Package structure    : importable")
    except ImportError as exc:
        print(f"[FAIL] Package structure broken: {exc}")
        return 1

    # ---- Writable data/uploads ----
    for folder in ("data", "uploads"):
        p = root / folder
        p.mkdir(exist_ok=True)
        probe = p / ".write_test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print(f"[OK]   {folder}/ writable")
        except OSError as exc:
            print(f"[FAIL] {folder}/ not writable: {exc}")
            return 1

    print("=" * 56)
    print(" Phase 1 complete. Ready for Phase 2 (SQLite).")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())