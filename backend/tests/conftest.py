"""Test setup: isolated data dir, fixture loaders. Tests never touch the network."""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["ADSPY_DATA_DIR"] = tempfile.mkdtemp(prefix="adspy-test-")

FIXTURES = BACKEND / "tests" / "fixtures"
# Fixtures were captured on this date; pin "today" so day counts are deterministic.
FIXTURE_TODAY = date(2026, 10, 4)


def read_fixture(name: str) -> str:
    path = FIXTURES / name
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def page_html() -> str:
    return read_fixture("gymshark_page.html.gz")


@pytest.fixture(scope="session")
def xhr_payloads() -> list[str]:
    return json.loads(read_fixture("gymshark_xhr.json.gz"))


@pytest.fixture(scope="session")
def selectors() -> dict:
    from app.core.config import get_selectors

    return get_selectors()


@pytest.fixture(scope="session")
def migrated_db():
    from app.db.session import run_migrations

    run_migrations()
    return True
