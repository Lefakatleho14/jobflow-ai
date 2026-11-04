"""
Pytest configuration.

We load `.env` once at test session start so that tests can read
production config if they want to — but tests that need isolation use
`monkeypatch.setenv` / `monkeypatch.delenv` to override specific vars,
and services no longer reload the file on every instantiation.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")