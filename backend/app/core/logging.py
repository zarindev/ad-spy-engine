"""Structured logging: console + rotating app log + one log file per scan (viewable in the UI)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.paths import logs_dir

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO, console: bool = True) -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger()
    root.setLevel(level)
    file_handler = RotatingFileHandler(
        logs_dir() / "app.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(file_handler)
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        stream.setLevel(logging.WARNING)
        root.addHandler(stream)
    for noisy in ("selenium", "urllib3", "httpx", "httpcore", "WDM", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def scan_log_path(scan_id: int) -> Path:
    return logs_dir() / f"scan-{scan_id}.log"


@contextmanager
def scan_log(scan_id: int) -> Iterator[Path]:
    """Attach a per-scan file handler for the duration of a scan (thread-filtered)."""
    import threading

    path = scan_log_path(scan_id)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMAT))
    thread_id = threading.get_ident()
    handler.addFilter(lambda record: record.thread == thread_id)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield path
    finally:
        root.removeHandler(handler)
        handler.close()
