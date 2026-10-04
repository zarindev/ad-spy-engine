"""Background scan worker: one scan at a time on a dedicated thread, backed by the `scan` table.

The `scan` table doubles as the job queue: rows are `queued` until the worker picks them up.
On startup, `running` scans become `interrupted` (the browser died with the process) and
`queued` scans are re-enqueued, so nothing is silently lost across restarts.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlmodel import select

from app.db.models import Scan, ScanStatus, utcnow
from app.db.session import session_scope
from app.jobs.events import bus
from app.jobs.runner import run_scan, scan_summary

log = logging.getLogger(__name__)


class BusLogHandler(logging.Handler):
    """Streams log records from the scan thread to the live log console."""

    def __init__(self, scan_id: int, thread_id: int) -> None:
        super().__init__(logging.INFO)
        self.scan_id = scan_id
        self.thread_id = thread_id

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self.thread_id:
            return
        try:
            bus.publish(
                self.scan_id,
                "log",
                {"level": record.levelname.lower(), "message": record.getMessage(), "logger": record.name},
            )
        except Exception:  # noqa: BLE001
            pass


class ScanWorker:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-worker")
        self.cancels: dict[int, threading.Event] = {}
        self.current: int | None = None
        self.shutting_down = False
        self._lock = threading.Lock()

    def enqueue(self, scan_id: int) -> None:
        with self._lock:
            self.cancels[scan_id] = threading.Event()
        bus.publish(scan_id, "status", {"status": ScanStatus.QUEUED})
        self.executor.submit(self._run, scan_id)

    def cancel(self, scan_id: int) -> bool:
        with self._lock:
            event = self.cancels.get(scan_id)
        if event is None:
            return False
        event.set()
        if self.current != scan_id:  # still waiting in the queue
            with session_scope() as session:
                scan = session.get(Scan, scan_id)
                if scan and scan.status == ScanStatus.QUEUED:
                    scan.status, scan.finished_at = ScanStatus.CANCELLED, utcnow()
                    session.add(scan)
                    session.commit()
                    bus.publish(scan_id, "status", {"status": scan.status, "scan": scan_summary(scan)})
        return True

    def _run(self, scan_id: int) -> None:
        cancel = self.cancels.get(scan_id) or threading.Event()
        with session_scope() as session:
            scan = session.get(Scan, scan_id)
            if scan is None or scan.status != ScanStatus.QUEUED or cancel.is_set():
                self.cancels.pop(scan_id, None)
                return
        handler = BusLogHandler(scan_id, threading.get_ident())
        logging.getLogger().addHandler(handler)
        self.current = scan_id

        def on_event(kind: str, data: dict[str, Any]) -> None:
            if kind != "log":  # log lines arrive through BusLogHandler
                bus.publish(scan_id, kind, data)

        try:
            scan = run_scan(scan_id, on_event=on_event, cancel=cancel)
            self._maybe_alert(scan)
            if self.shutting_down and scan.status == ScanStatus.CANCELLED:
                with session_scope() as session:
                    row = session.get(Scan, scan_id)
                    if row is not None:
                        row.status = ScanStatus.INTERRUPTED
                        row.error = "The app was closed during this scan. Collected ads were kept."
                        session.add(row)
                        session.commit()
        except Exception:  # noqa: BLE001
            log.exception("Worker crashed while running scan %s", scan_id)
            with session_scope() as session:
                scan = session.get(Scan, scan_id)
                if scan and scan.status not in ScanStatus.FINISHED:
                    scan.status, scan.finished_at = ScanStatus.FAILED, utcnow()
                    scan.error = "Unexpected worker error — see the scan log."
                    session.add(scan)
                    session.commit()
                    bus.publish(scan_id, "status", {"status": scan.status, "scan": scan_summary(scan)})
        finally:
            logging.getLogger().removeHandler(handler)
            self.current = None
            self.cancels.pop(scan_id, None)

    def _maybe_alert(self, scan: Scan) -> None:
        """Scheduled scans alert on changes (or on a block/failure) when the item has notify on."""
        if scan.trigger != "schedule":
            return
        from app.analysis.changes import has_changes
        from app.db.models import WatchlistItem
        from app.notify import channels, send_alert

        try:
            with session_scope() as session:
                item = session.exec(
                    select(WatchlistItem).where(WatchlistItem.competitor_id == scan.competitor_id)
                ).first()
                if item is None or not item.notify or not any(channels().values()):
                    return
                fresh = session.get(Scan, scan.id)
                if fresh is None:
                    return
                if fresh.status in (ScanStatus.BLOCKED, ScanStatus.FAILED) or has_changes(
                    fresh.change_summary or {}
                ):
                    send_alert(session, fresh)
        except Exception:  # noqa: BLE001
            log.exception("Sending alert for scan %s failed", scan.id)

    def recover(self) -> dict[str, int]:
        """Called on startup."""
        interrupted = requeued = 0
        with session_scope() as session:
            for scan in session.exec(select(Scan).where(Scan.status == ScanStatus.RUNNING)).all():
                scan.status, scan.finished_at = ScanStatus.INTERRUPTED, utcnow()
                scan.error = "The app stopped while this scan was in progress."
                session.add(scan)
                interrupted += 1
            session.commit()
            queued = session.exec(
                select(Scan.id).where(Scan.status == ScanStatus.QUEUED).order_by(Scan.id)
            ).all()
        for scan_id in queued:
            self.enqueue(scan_id)
            requeued += 1
        return {"interrupted": interrupted, "requeued": requeued}

    def shutdown(self, timeout: float = 30.0) -> None:
        """Stop gracefully: cancel queued work, let the running scan close its browser."""
        self.shutting_down = True
        for event in list(self.cancels.values()):
            event.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
        done = threading.Event()

        def drain() -> None:
            self.executor.shutdown(wait=True)
            done.set()

        threading.Thread(target=drain, daemon=True).start()
        if not done.wait(timeout):
            log.warning("Scan worker did not stop within %.0fs", timeout)


worker = ScanWorker()
