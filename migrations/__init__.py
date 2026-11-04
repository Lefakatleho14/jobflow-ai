"""
Migration framework for JobFlow AI.

Forward-only. Every schema change is a numbered file in this package.
`run_migrations()` finds unapplied migrations, applies them in order,
and records them in the `schema_migrations` table.

Design rules (see migrations/README.md):
    * Never edit an applied migration. Add a new one instead.
    * Never drop a column. Add a "superseded" column and stop reading it.
    * Never rename a column in-place. Add new, backfill, deprecate.
    * Migrations must be idempotent-safe (running twice must not error).
    * Migrations must not depend on app code (models, services). Only
      raw SQL and the engine. This keeps them decoupled from refactors.
"""

from __future__ import annotations

import importlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent


def _discover_migrations() -> list[str]:
    """
    Return migration ids (filename stems) sorted by their leading 3-digit
    numeric prefix. Files must start with three digits + underscore.
    """
    ids: list[str] = []
    for path in MIGRATIONS_DIR.glob("*.py"):
        name = path.stem
        if name.startswith("__"):
            continue
        if len(name) < 4 or not name[:3].isdigit() or name[3] != "_":
            logger.warning("Skipping malformed migration file: %s", name)
            continue
        ids.append(name)
    return sorted(ids)


def _ensure_table(engine: Engine) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at DATETIME NOT NULL,
                duration_ms INTEGER NOT NULL
            )
            """
        ))


def get_applied_migrations(engine: Engine) -> list[str]:
    """Return migration ids already applied, in insertion order."""
    _ensure_table(engine)
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id FROM schema_migrations ORDER BY applied_at"
        )).fetchall()
    return [r[0] for r in rows]


def get_pending_migrations(engine: Engine) -> list[str]:
    """Return migration ids discovered but not yet applied."""
    discovered = _discover_migrations()
    applied = set(get_applied_migrations(engine))
    return [m for m in discovered if m not in applied]


def _load_migration(migration_id: str) -> tuple[Callable, Optional[Callable]]:
    """Return (up_fn, down_fn) for a migration id."""
    module = importlib.import_module(f"migrations.{migration_id}")
    if not hasattr(module, "up"):
        raise RuntimeError(f"Migration {migration_id} missing up() function")
    up_fn = getattr(module, "up")
    down_fn = getattr(module, "down", None)
    return up_fn, down_fn


def run_migrations(engine: Engine) -> list[str]:
    """
    Apply all pending migrations in order. Returns the list of ids
    applied during this call (empty if already up to date).
    """
    _ensure_table(engine)
    pending = get_pending_migrations(engine)
    if not pending:
        logger.info("No pending migrations.")
        return []

    applied_now: list[str] = []
    for mid in pending:
        up_fn, _ = _load_migration(mid)
        logger.info("Applying migration: %s", mid)
        start = time.perf_counter()
        try:
            up_fn(engine)
        except Exception:
            logger.exception("Migration failed: %s", mid)
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO schema_migrations (id, applied_at, duration_ms) "
                "VALUES (:id, :applied_at, :duration_ms)"
            ), {
                "id": mid,
                "applied_at": datetime.now(timezone.utc),
                "duration_ms": duration_ms,
            })
        applied_now.append(mid)
        logger.info("Applied: %s (%d ms)", mid, duration_ms)

    return applied_now


def status(engine: Engine) -> dict:
    """Return a summary dict: discovered, applied, pending, plus durations."""
    _ensure_table(engine)
    discovered = _discover_migrations()
    applied_rows: list[dict] = []
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, applied_at, duration_ms FROM schema_migrations ORDER BY applied_at"
        )).fetchall()
    for r in rows:
        applied_rows.append({"id": r[0], "applied_at": r[1], "duration_ms": r[2]})
    applied_ids = {r["id"] for r in applied_rows}
    pending = [m for m in discovered if m not in applied_ids]
    return {
        "discovered": discovered,
        "applied": applied_rows,
        "pending": pending,
    }