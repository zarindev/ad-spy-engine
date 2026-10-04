from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.serializers import report_out
from app.core.paths import data_dir
from app.db.models import Client, Competitor, Report, Scan
from app.db.session import session_scope
from app.reports.builder import DEFAULT_SECTIONS, SECTIONS, ReportSpec, normalize_sections, render_report
from app.reports.pdf import html_to_pdf
from app.scraper.media import relative_to_data

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportCreate(BaseModel):
    kind: Literal["scan", "competitor", "compare", "client"] = "scan"
    scan_id: int | None = None
    competitor_ids: list[int] = Field(default_factory=list, max_length=12)
    client_id: int | None = None
    client_name: str | None = Field(None, max_length=80)
    title: str | None = Field(None, max_length=120)
    sections: list[str] = Field(default_factory=lambda: list(DEFAULT_SECTIONS))
    top_n: int = Field(10, ge=3, le=50)
    ai: bool = False
    days: int = Field(30, ge=1, le=365)
    own_only: bool = True
    pdf: bool = True


def _resolve(body: ReportCreate) -> tuple[ReportSpec, list[int], str]:
    """Turn a request into a builder spec, validating the scope. Returns (spec, competitor ids, title)."""
    client_name = (body.client_name or "").strip() or None
    with session_scope() as session:
        if body.kind == "scan":
            scan = session.get(Scan, body.scan_id) if body.scan_id else None
            if scan is None:
                raise HTTPException(404, "Scan not found")
            ids = [scan.competitor_id]
        elif body.kind == "client":
            client = session.get(Client, body.client_id) if body.client_id else None
            if client is None:
                raise HTTPException(404, "Client not found")
            ids = list(session.exec(select(Competitor.id).where(Competitor.client_id == client.id)).all())  # type: ignore[arg-type]
            if not ids:
                raise HTTPException(
                    422, f"“{client.name}” has no competitors yet. Add some on the Competitors page."
                )
            client_name = client_name or client.name
        else:
            ids = list(dict.fromkeys(body.competitor_ids))
            if not ids:
                raise HTTPException(422, "Pick at least one competitor")
            if body.kind == "compare" and not 2 <= len(ids) <= 3:
                raise HTTPException(422, "A comparison report needs 2 or 3 competitors")
        names = []
        for cid in ids:
            comp = session.get(Competitor, cid)
            if comp is None:
                raise HTTPException(404, f"Competitor {cid} not found")
            names.append(comp.name)
    sections = normalize_sections(body.sections)
    if not sections:
        raise HTTPException(422, "Pick at least one section")
    default_title = names[0] if len(names) == 1 else " vs ".join(names[:3]) + ("…" if len(names) > 3 else "")
    if body.kind == "client" and client_name:
        default_title = f"{client_name}: competitor landscape"
    title = (body.title or "").strip() or default_title
    spec = ReportSpec(
        competitor_ids=ids,
        scan_id=body.scan_id if body.kind == "scan" else None,
        title=title,
        client_name=client_name,
        sections=sections,
        top_n=body.top_n,
        use_ai=body.ai,
        days=body.days,
        own_only=body.own_only,
    )
    return spec, ids, title


def _generate(body: ReportCreate) -> dict:
    spec, ids, title = _resolve(body)
    report = Report(
        title=title,
        kind=body.kind,
        scan_id=spec.scan_id,
        competitor_ids=ids,
        options={
            "sections": spec.sections,
            "top_n": spec.top_n,
            "client_name": spec.client_name,
            "client_id": body.client_id,
            "ai": body.ai,
            "days": spec.days,
            "own_only": spec.own_only,
        },
    )
    with session_scope() as session:
        session.add(report)
        session.commit()
        session.refresh(report)

    try:
        html_path, meta = render_report(spec)
        report.html_path = relative_to_data(html_path)
        report.options = {**report.options, **meta}
        if body.pdf:
            pdf_path = html_to_pdf(html_path, html_path.with_suffix(".pdf"))
            report.pdf_path = relative_to_data(pdf_path)
    except Exception as exc:  # noqa: BLE001
        log.exception("Report generation failed")
        report.status, report.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
    with session_scope() as session:
        session.add(report)
        session.commit()
        session.refresh(report)
    return report_out(report)


@router.get("/sections")
def sections() -> dict:
    return {"all": SECTIONS, "default": DEFAULT_SECTIONS}


@router.post("", status_code=201)
async def create_report(body: ReportCreate) -> dict:
    return await run_in_threadpool(_generate, body)


@router.get("")
def list_reports(limit: int = 50) -> list[dict]:
    with session_scope() as session:
        rows = session.exec(select(Report).order_by(Report.id.desc()).limit(limit)).all()
    return [report_out(r) for r in rows]


@router.delete("/{report_id}")
def delete_report(report_id: int) -> dict:
    with session_scope() as session:
        report = session.get(Report, report_id)
        if report is None:
            raise HTTPException(404, "Report not found")
        for rel in (report.html_path, report.pdf_path):
            if rel:
                Path(data_dir() / rel).unlink(missing_ok=True)
        session.delete(report)
        session.commit()
    return {"ok": True}
