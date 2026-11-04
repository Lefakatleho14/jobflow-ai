"""
Allow `python -m migrations` as a CLI.
Delegates to migrations.cli:main().
"""

from migrations.cli import main

if __name__ == "__main__":
    raise SystemExit(main())