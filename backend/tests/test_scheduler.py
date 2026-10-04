from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import Competitor, Scan, WatchlistItem
from app.db.session import session_scope
from app.jobs import scheduler as sched_mod
from app.jobs.scheduler import WatchlistScheduler, compute_next_run


def test_daily_and_weekly_next_run(monkeypatch):
    tz = ZoneInfo("Asia/Dhaka")
    monkeypatch.setattr(sched_mod, "get_localzone", lambda: tz)
    now = datetime(2026, 10, 4, 10, 30, tzinfo=tz)  # Sunday
    daily = WatchlistItem(competitor_id=1, query="x", frequency="daily", hour=9, minute=0)
    assert compute_next_run(daily, now) == datetime(2026, 10, 5, 9, 0, tzinfo=tz).astimezone(UTC)
    later_today = WatchlistItem(competitor_id=1, query="x", frequency="daily", hour=18, minute=15)
    assert compute_next_run(later_today, now) == datetime(2026, 10, 4, 18, 15, tzinfo=tz).astimezone(UTC)
    weekly = WatchlistItem(competitor_id=1, query="x", frequency="weekly", weekday=2, hour=8)  # Wednesday
    assert compute_next_run(weekly, now) == datetime(2026, 10, 7, 8, 0, tzinfo=tz).astimezone(UTC)


def test_run_item_queues_scheduled_scan_and_catch_up(migrated_db, monkeypatch):
    from app.jobs.worker import worker

    queued: list[int] = []
    monkeypatch.setattr(worker, "enqueue", queued.append)
    with session_scope() as s:
        comp = Competitor(name="Sched Brand", slug="sched-brand")
        s.add(comp)
        s.flush()
        item = WatchlistItem(
            competitor_id=comp.id, query="Sched Brand", next_run_at=datetime.now(UTC) - timedelta(hours=2)
        )
        s.add(item)
        s.commit()
        item_id, comp_id = item.id, comp.id

    ws = WatchlistScheduler()
    assert ws.catch_up() >= 1
    assert len(queued) >= 1
    with session_scope() as s:
        scan = s.get(Scan, queued[-1])
        assert scan.trigger == "schedule" and scan.competitor_id == comp_id
        item = s.get(WatchlistItem, item_id)
        assert item.last_scan_id == scan.id and item.next_run_at is not None
    # a second run while the first is still queued is skipped
    assert ws.run_item(item_id) is None
