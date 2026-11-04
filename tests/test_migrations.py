"""
Phase 7.5 tests: migration framework, schema_migrations table, 001 migration.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.database.base import Base
from app.models import Job
from migrations import (
    get_applied_migrations,
    get_pending_migrations,
    run_migrations,
    status,
)


@pytest.fixture()
def legacy_engine():
    """
    Build an engine that has the *pre-7.5* jobs table (no new columns).
    Simulates an existing database that needs migration.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="jobflow_mig_"))
    db_file = tmp_dir / "legacy.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", future=True)

    # Create only the original jobs table (pre-7.5 schema), plus the bare
    # minimum others so foreign keys resolve if needed.
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                external_id TEXT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                remote_status TEXT,
                description TEXT,
                url TEXT,
                source TEXT,
                date_found DATETIME,
                date_posted DATETIME,
                status TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_currency TEXT,
                content_hash TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO jobs (id, title, company, location, status)
            VALUES ('legacy-1', 'Legacy Job', 'Legacy Co', 'Somewhere', 'discovered')
        """))

    yield engine
    engine.dispose()


def test_migrations_table_created_after_first_run(legacy_engine):
    run_migrations(legacy_engine)
    inspector = inspect(legacy_engine)
    assert "schema_migrations" in inspector.get_table_names()


def test_migration_001_adds_columns(legacy_engine):
    run_migrations(legacy_engine)
    inspector = inspect(legacy_engine)
    cols = {c["name"] for c in inspector.get_columns("jobs")}
    for name in (
        "country", "employment_type", "seniority", "date_posted_status",
        "closing_date", "closing_date_status", "availability_status",
        "date_last_verified",
    ):
        assert name in cols, f"Missing column: {name}"


def test_migration_001_backfills_availability(legacy_engine):
    run_migrations(legacy_engine)
    with legacy_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT availability_status FROM jobs WHERE id = 'legacy-1'"
        )).fetchone()
    assert row[0] == "unverified"


def test_migration_001_preserves_existing_rows(legacy_engine):
    run_migrations(legacy_engine)
    with legacy_engine.begin() as conn:
        row = conn.execute(text(
            "SELECT title, company FROM jobs WHERE id = 'legacy-1'"
        )).fetchone()
    assert row[0] == "Legacy Job"
    assert row[1] == "Legacy Co"


def test_migration_is_idempotent(legacy_engine):
    first = run_migrations(legacy_engine)
    second = run_migrations(legacy_engine)
    assert len(first) == 1
    assert second == []


def test_applied_contains_001(legacy_engine):
    run_migrations(legacy_engine)
    applied = get_applied_migrations(legacy_engine)
    assert "001_add_verification_fields" in applied


def test_pending_empty_after_run(legacy_engine):
    run_migrations(legacy_engine)
    assert get_pending_migrations(legacy_engine) == []


def test_status_reports_counts(legacy_engine):
    run_migrations(legacy_engine)
    s = status(legacy_engine)
    assert len(s["discovered"]) >= 1
    assert len(s["applied"]) >= 1
    assert s["pending"] == []


def test_orm_model_has_new_fields():
    """The ORM model must declare the new columns, matching the migration."""
    cols = {c.name for c in Job.__table__.columns}
    for name in (
        "country", "employment_type", "seniority", "date_posted_status",
        "closing_date", "closing_date_status", "availability_status",
        "date_last_verified",
    ):
        assert name in cols, f"Job model missing column: {name}"