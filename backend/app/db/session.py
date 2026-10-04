"""Engine/session helpers and programmatic Alembic upgrade."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.paths import BACKEND_DIR, db_path

log = logging.getLogger(__name__)


def database_url() -> str:
    return f"sqlite:///{db_path().as_posix()}"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(database_url(), connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def run_migrations() -> None:
    """Bring the SQLite schema up to date (idempotent, called on every start)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url())
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
