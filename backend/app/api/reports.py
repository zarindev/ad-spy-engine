from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.serializers import report_out
from app.core.paths import data_dir
from app.db.models import Competitor, Report, Scan
from app.db.session import session_scope
from app.reports.builder import build_scan_report
from app.reports.pdf import html_to_pdf
from app.scraper.media import relative_to_data

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])

SECTIONS = ["summary", "charts", "top_ads", "all_ads"]


class ReportCreate(BaseModel):
    scan_id: int
    title: str | None = Field(None, max_length=120)
    sections: list[str] = Field(default_factory=lambda: list(SECTIONS))
    top_n: int = Field(30, ge=3, le=100)
    pdf: bool = True


def _generate(body: ReportCreate) -> dict:
    with session_scope() as session:
        scan = session.get(Scan, body.scan_id)
        if scan is None:
            raise HTTPException(404, "Scan not found")
        comp = session.get(Competitor, scan.competitor_id)
        title = body.title or f"{comp.name if comp else 'Scan'} — Ad Report"
        report = Report(
            title=title,
            kind="scan",
            scan_id=scan.id,
            competitor_ids=[scan.competitor_id],
            options={"sections": [s for s in body.sections if s in SECTIONS], "top_n": body.top_n},
        )
        session.add(report)
        session.commit()
        session.refresh(report)

    try:
        html_path = build_scan_report(
            body.scan_id, options={**report.options, "title": body.title or (comp.name if comp else None)}
        )
        report.html_path = relative_to_data(html_path)
        if body.pdf:
            pdf_path = html_to_pdf(html_path, html_path.with_suffix(".pdf"))
            report.pdf_path = relative_to_data(pdf_path)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("Report generation failed")
        report.status, report.error = "failed", f"{type(exc).__name__}: {exc}"
    with session_scope() as session:
        session.add(report)
        session.commit()
        session.refresh(report)
    return report_out(report)


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
