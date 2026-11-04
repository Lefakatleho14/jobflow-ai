
### 5.6 `migrations/001_add_verification_fields.py`

"""
001 — Add verification and internationalization fields to `jobs`.

New columns:
    country               TEXT NULL
    employment_type       TEXT NULL
    seniority             TEXT NULL
    date_posted_status    TEXT NULL
    closing_date          DATETIME NULL
    closing_date_status   TEXT NULL
    availability_status   TEXT NULL
    date_last_verified    DATETIME NULL

Backfill:
    availability_status -> 'unverified' for existing rows

Idempotent: safe to run more than once (checks PRAGMA table_info first).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


NEW_COLUMNS = [
    # (name, sql_type)
    ("country",             "TEXT"),
    ("employment_type",     "TEXT"),
    ("seniority",           "TEXT"),
    ("date_posted_status",  "TEXT"),
    ("closing_date",        "DATETIME"),
    ("closing_date_status", "TEXT"),
    ("availability_status", "TEXT"),
    ("date_last_verified",  "DATETIME"),
]


def _column_names(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}  # index 1 is the column name


def up(engine: Engine) -> None:
    with engine.begin() as conn:
        existing = _column_names(conn, "jobs")
        for name, type_ in NEW_COLUMNS:
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {type_}"))

        # Backfill availability_status for rows that predate this migration.
        conn.execute(text(
            "UPDATE jobs SET availability_status = 'unverified' "
            "WHERE availability_status IS NULL"
        ))


def down(engine: Engine) -> None:
    raise NotImplementedError(
        "Column drops are not supported in SQLite. See migrations/README.md"
    )