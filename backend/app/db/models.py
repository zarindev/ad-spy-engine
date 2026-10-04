"""Database models (SQLModel). Schema changes go through Alembic: `alembic revision --autogenerate`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Column, LargeBinary, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class ScanStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

    FINISHED = {COMPLETED, FAILED, BLOCKED, CANCELLED, INTERRUPTED}


class Competitor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    page_id: str | None = Field(default=None, index=True)
    logo_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_scan_at: datetime | None = None


class Scan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    competitor_id: int = Field(foreign_key="competitor.id", index=True)
    query: str
    search_type: str = "keyword"  # keyword | page_id
    country: str = "US"
    media_type: str = "all"
    platforms: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active_status: str = "active"
    max_ads: int = 200
    exact_page: bool = False  # keyword mode: keep only ads whose page name matches the query
    headless: bool = True

    status: str = Field(default=ScanStatus.QUEUED, index=True)
    total_results: int | None = None
    ads_found: int = 0
    ads_processed: int = 0
    ads_failed: int = 0
    new_ads: int = 0
    error: str | None = None
    block_reason: str | None = None
    log_path: str | None = None

    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class Ad(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    library_id: str = Field(index=True, unique=True)
    competitor_id: int = Field(foreign_key="competitor.id", index=True)

    page_name: str | None = None
    page_id: str | None = Field(default=None, index=True)
    page_profile_image: str | None = None

    status: str = "active"  # active | inactive
    start_date: date | None = None
    end_date: date | None = None
    days_running: int = 0
    platforms: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    ad_copy: str | None = None
    headline: str | None = None
    description: str | None = None
    cta_text: str | None = None
    cta_type: str | None = None
    landing_url: str | None = None
    display_format: str | None = None
    media_type: str = "image"  # image | video | carousel | dynamic | catalog | text
    media_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    thumbnail_url: str | None = None
    variation_count: int = 1
    collation_id: str | None = None

    screenshot_path: str | None = None  # relative to data dir
    thumbnail_path: str | None = None
    media_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    raw_html: bytes | None = Field(default=None, sa_column=Column(LargeBinary))  # zlib
    raw_json: bytes | None = Field(default=None, sa_column=Column(LargeBinary))  # zlib
    source: str = "json"  # json | dom | json+dom

    score: int = Field(default=0, index=True)
    score_breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)
    last_scan_id: int | None = Field(default=None, foreign_key="scan.id")


class AdSnapshot(SQLModel, table=True):
    """One row per ad per scan — the basis of change detection."""

    __table_args__ = (UniqueConstraint("ad_id", "scan_id"),)

    id: int | None = Field(default=None, primary_key=True)
    ad_id: int = Field(foreign_key="ad.id", index=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    status: str = "active"
    variation_count: int = 1
    days_running: int = 0
    score: int = 0
    captured_at: datetime = Field(default_factory=utcnow)
