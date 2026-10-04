from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.serializers import asset_url
from app.core.demo import require_live
from app.db.models import Competitor, Scan, WatchlistItem
from app.db.session import session_scope
from app.jobs.scheduler import scheduler

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class Schedule(BaseModel):
    frequency: Literal["daily", "weekly"] = "daily"
    hour: int = Field(9, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    weekday: int = Field(0, ge=0, le=6)
    notify: bool = True
    enabled: bool = True


class WatchCreate(Schedule):
    competitor_id: int
    country: str | None = None
    media_type: str | None = None
    max_ads: int | None = Field(None, ge=10, le=5000)


class WatchUpdate(BaseModel):
    frequency: Literal["daily", "weekly"] | None = None
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    weekday: int | None = Field(None, ge=0, le=6)
    notify: bool | None = None
    enabled: bool | None = None
    max_ads: int | None = Field(None, ge=10, le=5000)
    country: str | None = None


def item_out(item: WatchlistItem, comp: Competitor | None, last: Scan | None) -> dict[str, Any]:
    return {
        "id": item.id,
        "competitor_id": item.competitor_id,
        "competitor_name": comp.name if comp else None,
        "competitor_logo": asset_url(comp.logo_url) if comp else None,
        "query": item.query,
        "search_type": item.search_type,
        "country": item.country,
        "media_type": item.media_type,
        "max_ads": item.max_ads,
        "exact_page": item.exact_page,
        "frequency": item.frequency,
        "hour": item.hour,
        "minute": item.minute,
        "weekday": item.weekday,
        "enabled": item.enabled,
        "notify": item.notify,
        "next_run_at": item.next_run_at.isoformat() if item.next_run_at else None,
        "last_run_at": item.last_run_at.isoformat() if item.last_run_at else None,
        "last_scan": (
            {
                "id": last.id,
                "status": last.status,
                "ads_found": last.ads_found,
                "change_summary": last.change_summary or {},
            }
            if last
            else None
        ),
    }


def _load(item_id: int) -> dict[str, Any]:
    with session_scope() as session:
        item = session.get(WatchlistItem, item_id)
        if item is None:
            raise HTTPException(404, "Watchlist item not found")
        return item_out(
            item,
            session.get(Competitor, item.competitor_id),
            session.get(Scan, item.last_scan_id) if item.last_scan_id else None,
        )


@router.get("")
def list_items() -> list[dict]:
    with session_scope() as session:
        items = session.exec(select(WatchlistItem).order_by(WatchlistItem.next_run_at)).all()
        return [
            item_out(
                i,
                session.get(Competitor, i.competitor_id),
                session.get(Scan, i.last_scan_id) if i.last_scan_id else None,
            )
            for i in items
        ]


@router.post("", status_code=201)
def add_item(body: WatchCreate) -> dict:
    with session_scope() as session:
        comp = session.get(Competitor, body.competitor_id)
        if comp is None:
            raise HTTPException(404, "Competitor not found")
        if session.exec(select(WatchlistItem).where(WatchlistItem.competitor_id == comp.id)).first():
            raise HTTPException(409, f"{comp.name} is already on the watchlist")
        template = session.exec(
            select(Scan).where(Scan.competitor_id == comp.id).order_by(Scan.id.desc())
        ).first()
        if template is None and not comp.page_id:
            raise HTTPException(422, "Scan this competitor once before adding it to the watchlist")
        item = WatchlistItem(
            competitor_id=comp.id,
            query=template.query if template else comp.page_id,  # type: ignore[arg-type]
            search_type=template.search_type if template else "page_id",
            country=(body.country or (template.country if template else "US")).upper(),
            media_type=body.media_type or (template.media_type if template else "all"),
            max_ads=body.max_ads or (template.max_ads if template else 200),
            exact_page=template.exact_page if template else False,
            **body.model_dump(include={"frequency", "hour", "minute", "weekday", "notify", "enabled"}),
        )
        session.add(item)
        session.commit()
        item_id = item.id
    scheduler.sync()
    return _load(item_id)  # type: ignore[arg-type]


@router.patch("/{item_id}")
def update_item(item_id: int, body: WatchUpdate) -> dict:
    with session_scope() as session:
        item = session.get(WatchlistItem, item_id)
        if item is None:
            raise HTTPException(404, "Watchlist item not found")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(item, key, value.upper() if key == "country" else value)
        session.add(item)
        session.commit()
    scheduler.sync()
    return _load(item_id)


@router.delete("/{item_id}")
def delete_item(item_id: int) -> dict:
    with session_scope() as session:
        item = session.get(WatchlistItem, item_id)
        if item is None:
            raise HTTPException(404, "Watchlist item not found")
        session.delete(item)
        session.commit()
    scheduler.sync()
    return {"ok": True}


@router.post("/{item_id}/run")
def run_now(item_id: int) -> dict:
    require_live()
    scan_id = scheduler.run_item(item_id)
    if scan_id is None:
        raise HTTPException(409, "A scan for this competitor is already queued or running")
    return {"scan_id": scan_id, **_load(item_id)}
