"""Filesystem locations. Everything goes through pathlib so Windows and POSIX behave the same."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = ROOT_DIR / "backend"
CONFIG_DIR = ROOT_DIR / "config"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
TEMPLATES_DIR = BACKEND_DIR / "app" / "reports" / "templates"


def data_dir() -> Path:
    custom = os.environ.get("ADSPY_DATA_DIR", "").strip()
    path = Path(custom).expanduser() if custom else ROOT_DIR / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def media_dir() -> Path:
    return _sub("media")


def reports_dir() -> Path:
    return _sub("reports")


def logs_dir() -> Path:
    return _sub("logs")


def db_path() -> Path:
    return data_dir() / "app.db"


def _sub(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str, max_len: int = 60) -> str:
    """Filesystem-safe slug (also safe for Windows reserved characters)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug or "untitled")[:max_len]
