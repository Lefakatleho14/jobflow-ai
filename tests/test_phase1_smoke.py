"""
Phase 1 smoke tests.

These tests do NOT touch business logic.
They only verify that the project skeleton is sound.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_project_root_exists() -> None:
    assert PROJECT_ROOT.is_dir()


def test_expected_directories_exist() -> None:
    expected = [
        "app",
        "app/api",
        "app/ai",
        "app/database",
        "app/models",
        "app/services",
        "app/services/jobs",
        "app/services/matching",
        "app/services/cv",
        "app/services/notifications",
        "app/automation",
        "app/utils",
        "frontend",
        "tests",
        "scripts",
        "data",
        "uploads",
        "workflows",
        "workflows/n8n",
    ]
    for rel in expected:
        path = PROJECT_ROOT / rel
        assert path.is_dir(), f"Missing directory: {rel}"


def test_packages_have_init_files() -> None:
    packages = [
        "app",
        "app/api",
        "app/ai",
        "app/database",
        "app/models",
        "app/services",
        "app/services/jobs",
        "app/services/matching",
        "app/services/cv",
        "app/services/notifications",
        "app/automation",
        "app/utils",
        "frontend",
        "tests",
    ]
    for pkg in packages:
        init = PROJECT_ROOT / pkg / "__init__.py"
        assert init.is_file(), f"Missing __init__.py in {pkg}"


def test_required_root_files_exist() -> None:
    for name in (
        "requirements.txt",
        ".gitignore",
        ".env.example",
        "main.py",
    ):
        assert (PROJECT_ROOT / name).is_file(), f"Missing root file: {name}"


def test_packages_importable() -> None:
    import app  # noqa: F401
    import app.services.jobs  # noqa: F401
    import app.services.matching  # noqa: F401
    import app.services.cv  # noqa: F401
    import app.services.notifications  # noqa: F401
    import app.automation  # noqa: F401
    import app.utils  # noqa: F401


def test_core_dependencies_importable() -> None:
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
    import sqlalchemy  # noqa: F401
    import dotenv  # noqa: F401
    import ollama  # noqa: F401
    import apscheduler  # noqa: F401
    import feedparser  # noqa: F401
    import httpx  # noqa: F401


@pytest.mark.parametrize("folder", ["data", "uploads"])
def test_writable_folders(folder: str) -> None:
    p = PROJECT_ROOT / folder
    assert p.is_dir()
    probe = p / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    assert probe.read_text(encoding="utf-8") == "ok"
    probe.unlink()