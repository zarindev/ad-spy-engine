"""Track browser processes so a hard crash never leaves Chrome running in the background.

Each driver's chromedriver PID and Chrome profile directory are recorded in data/run/drivers.json.
On the next start, anything still alive from that list is terminated.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import psutil

from app.core.paths import data_dir

log = logging.getLogger(__name__)
_lock = threading.Lock()


def _registry() -> Path:
    path = data_dir() / "run"
    path.mkdir(parents=True, exist_ok=True)
    return path / "drivers.json"


def _read() -> list[dict[str, Any]]:
    try:
        return json.loads(_registry().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _write(entries: list[dict[str, Any]]) -> None:
    _registry().write_text(json.dumps(entries), encoding="utf-8")


def describe(driver: Any) -> dict[str, Any]:
    service = getattr(driver, "service", None)
    process = getattr(service, "process", None)
    caps = getattr(driver, "capabilities", {}) or {}
    return {
        "pid": getattr(process, "pid", None),
        "user_data_dir": (caps.get("chrome") or {}).get("userDataDir"),
    }


def register(driver: Any) -> None:
    entry = describe(driver)
    if not entry["pid"]:
        return
    with _lock:
        entries = [e for e in _read() if e.get("pid") != entry["pid"]]
        _write([*entries, entry])


def unregister(driver: Any) -> None:
    pid = describe(driver)["pid"]
    with _lock:
        _write([e for e in _read() if e.get("pid") != pid])


def cleanup_orphans() -> int:
    """Terminate chromedriver/Chrome processes left behind by a crashed previous run."""
    with _lock:
        entries = _read()
        _write([])
    if not entries:
        return 0
    profiles = {e["user_data_dir"] for e in entries if e.get("user_data_dir")}
    pids = {e["pid"] for e in entries if e.get("pid")}
    victims: list[psutil.Process] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            name = (proc.info.get("name") or "").lower()
            if proc.info["pid"] in pids and "chromedriver" in name:
                victims.append(proc)
            elif profiles and any(p in cmdline for p in profiles):
                victims.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for proc in victims:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if victims:
        log.warning("Cleaned up %d orphaned browser processes from a previous run", len(victims))
    return len(victims)
