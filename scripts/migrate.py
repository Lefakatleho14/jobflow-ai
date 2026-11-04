"""
CLI wrapper: python scripts/migrate.py [--status]

Equivalent to `python -m migrations`. Provided for consistency with the
other scripts in this folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migrations.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())