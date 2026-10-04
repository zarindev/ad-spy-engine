"""Watchlist scheduler (APScheduler). Runs only while the app is open.

Each enabled watchlist item gets a cron job in the machine's local time zone (daily at HH:MM, or
weekly on a weekday). Runs that were due while the app was closed are caught up once on startup.
A run creates a normal scan with trigger="schedule" and puts it on the scan worker's queue, so
rate limiting and the one-scan-at-a-time rule still apply.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select
from tzlocal import get_localzone

from app.db.models import Competitor, Scan, WatchlistItem, utcnow
from app.db.session import session_scope

log = logging.getLogger(__name__)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def trigger_for(item: WatchlistItem) -> CronTrigger:
    tz = get_localzone()
    if item.frequency == "weekly":
        return CronTrigger(
            day_of_week=DAYS[item.weekday % 7], hour=item.hour, minute=item.minute, timezone=tz
        )
    return CronTrigger(hour=item.hour, minute=item.minute, timezone=tz)


def compute_next_run(item: WatchlistItem, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(get_localzone())
    fire = trigger_for(item).get_next_fire_time(None, now)
    return fire.astimezone(UTC) if fire else None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class WatchlistScheduler:
    def __init__(self) -> None:
        self.scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler(
                timezone=get_localzone(),
                job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
            )
            self.scheduler.start()
        self.catch_up()
        self.sync()

    def shutdown(self) -> None:
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

    def sync(self) -> None:
        """(Re)create one job per enabled item and store each item's next run time."""
        if self.scheduler is None:
            return
        self.scheduler.remove_all_jobs()
        with session_scope() as session:
            for item in session.exec(select(WatchlistItem)).all():
                if item.enabled:
                    self.scheduler.add_job(
                        self.run_item,
                        trigger_for(item),
                        args=[item.id],
                        id=f"watch-{item.id}",
                        replace_existing=True,
                    )
                    item.next_run_at = compute_next_run(item)
                else:
                    item.next_run_at = None
                session.add(item)
            session.commit()

    def catch_up(self) -> int:
        """Run items whose scheduled time passed while the app was closed (once each)."""
        now = utcnow()
        due: list[int] = []
        with session_scope() as session:
            for item in session.exec(
                select(WatchlistItem).where(WatchlistItem.enabled.is_(True))  # type: ignore[attr-defined]
            ).all():
                next_run = _as_utc(item.next_run_at)
                if next_run is not None and next_run <= now:
                    due.append(item.id)  # type: ignore[arg-type]
        for item_id in due:
            log.info("Catching up missed watchlist run for item %s", item_id)
            self.run_item(item_id)
        return len(due)

    def run_item(self, item_id: int) -> int | None:
        from app.jobs.runner import create_scan
        from app.jobs.worker import worker
        from app.scraper.ad_library import ScanParams

        with session_scope() as session:
            item = session.get(WatchlistItem, item_id)
            if item is None:
                return None
            busy = session.exec(
                select(Scan).where(Scan.competitor_id == item.competitor_id, Scan.status.in_(["queued", "running"]))  # type: ignore[attr-defined]
            ).first()
            if busy is not None:
                log.info("Skipping watchlist run for item %s: scan %s already in progress", item_id, busy.id)
                return None
            comp = session.get(Competitor, item.competitor_id)
            params = ScanParams(
                query=item.query,
                search_type=item.search_type,
                country=item.country,
                media_type=item.media_type,
                max_ads=item.max_ads,
                exact_page=item.exact_page,
                headless=True,
            )
            competitor_name = comp.name if comp else None

        scan = create_scan(params, competitor_name=competitor_name)
        with session_scope() as session:
            row = session.get(Scan, scan.id)
            if row is not None:
                row.trigger = "schedule"
                session.add(row)
            item = session.get(WatchlistItem, item_id)
            if item is not None:
                item.last_run_at = utcnow()
                item.last_scan_id = scan.id
                item.next_run_at = compute_next_run(item)
                session.add(item)
            session.commit()
        worker.enqueue(scan.id)
        log.info("Watchlist item %s queued scan %s", item_id, scan.id)
        return scan.id


scheduler = WatchlistScheduler()
