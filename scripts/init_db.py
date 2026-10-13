"""
CLI entrypoint:

    python scripts/init_db.py            # create if missing
    python scripts/init_db.py --reset    # drop and recreate (destructive)
    python scripts/init_db.py --list     # show current tables
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the project root importable when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DATABASE_URL  # noqa: E402
from app.database.init_db import (  # noqa: E402
    create_tables,
    database_is_initialized,
    list_tables,
    reset_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="JobFlow AI database initializer")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables")
    parser.add_argument("--list", action="store_true", help="List tables and exit")
    args = parser.parse_args()

    print("=" * 56)
    print(" JobFlow AI — Database initializer")
    print("=" * 56)
    print(f"[i]  URL: {DATABASE_URL}")

    if args.list:
        for name in list_tables():
            print(f"     - {name}")
        return 0

    if args.reset:
        print("[!]  Resetting database (dropping all tables)...")
        reset_database()
        print("[OK] Database reset and recreated.")
    else:
        print("[i]  Creating tables if missing...")
        create_tables()
        print("[OK] Tables created (or already existed).")

    print("[i]  Current tables:")
    for name in list_tables():
        print(f"     - {name}")

    if database_is_initialized():
        print("[OK] Database is fully initialized.")
        return 0
    print("[FAIL] Some expected tables are missing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())