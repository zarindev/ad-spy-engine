"""Server-Sent Events: live scan progress (per scan) and a global status stream."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.jobs.events import bus

router = APIRouter(prefix="/api", tags=["events"])


async def _stream(request: Request, scan_id: int | None) -> AsyncIterator[dict]:
    sub = bus.subscribe(scan_id)
    try:
        if scan_id is not None:
            for event in bus.history(scan_id):
                yield {"event": event["type"], "id": str(event["id"]), "data": json.dumps(event)}
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(sub.queue.get(), timeout=15)
            except TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": event["type"], "id": str(event["id"]), "data": json.dumps(event, default=str)}
    finally:
        bus.unsubscribe(sub)


@router.get("/scans/{scan_id}/events")
async def scan_events(scan_id: int, request: Request) -> EventSourceResponse:
    return EventSourceResponse(_stream(request, scan_id))


@router.get("/events")
async def global_events(request: Request) -> EventSourceResponse:
    return EventSourceResponse(_stream(request, None))
