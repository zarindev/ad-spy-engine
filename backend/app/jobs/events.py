"""Thread-safe in-process event bus bridging scan threads to async SSE subscribers."""

from __future__ import annotations

import asyncio
import itertools
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

# Events replayed to a client that connects mid-scan ("ad" events are fetched via REST instead).
REPLAY_TYPES = {"status", "progress", "log", "blocked"}


@dataclass
class Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]]
    scan_id: int | None  # None = global stream


class EventBus:
    def __init__(self, history_size: int = 400) -> None:
        self._lock = threading.Lock()
        self._subs: list[Subscriber] = []
        self._history: dict[int, deque[dict[str, Any]]] = {}
        self._seq = itertools.count(1)
        self._history_size = history_size

    def publish(self, scan_id: int, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        event = {"id": next(self._seq), "scan_id": scan_id, "type": kind, "data": data, "ts": time.time()}
        with self._lock:
            if kind in REPLAY_TYPES:
                self._history.setdefault(scan_id, deque(maxlen=self._history_size)).append(event)
            subs = list(self._subs)
        for sub in subs:
            if sub.scan_id is not None and sub.scan_id != scan_id:
                continue
            if sub.scan_id is None and kind not in {"status", "progress", "blocked"}:
                continue
            try:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, event)
            except RuntimeError:  # loop closed
                pass
        return event

    def history(self, scan_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history.get(scan_id, ()))

    def subscribe(self, scan_id: int | None = None) -> Subscriber:
        sub = Subscriber(asyncio.get_running_loop(), asyncio.Queue(maxsize=5000), scan_id)
        with self._lock:
            self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)


bus = EventBus()
