"""Background AI analysis runs (one at a time), tracked in the `airun` table."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlmodel import Session, select

from app.analysis import ai
from app.core.config import ai_model
from app.db.models import Ad, AiRun, utcnow
from app.db.session import session_scope

log = logging.getLogger(__name__)


def resolve_scope(session: Session, scope: dict[str, Any]) -> list[Ad]:
    stmt = select(Ad)
    if scope.get("ad_ids"):
        stmt = stmt.where(Ad.id.in_(scope["ad_ids"]))  # type: ignore[union-attr]
    if scope.get("competitor_id"):
        stmt = stmt.where(Ad.competitor_id == scope["competitor_id"])
    if scope.get("scan_id"):
        from app.db.models import AdSnapshot

        stmt = stmt.join(AdSnapshot, AdSnapshot.ad_id == Ad.id).where(AdSnapshot.scan_id == scope["scan_id"])
    if scope.get("only_winners"):
        from app.analysis.scoring import badge_range

        stmt = stmt.where(Ad.score >= badge_range("winner")[0])
    stmt = stmt.where(Ad.ad_copy.is_not(None))  # type: ignore[union-attr]
    stmt = stmt.order_by(Ad.score.desc()).limit(int(scope.get("limit") or 100))  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())


class AiWorker:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-worker")

    def start(self, scope: dict[str, Any]) -> AiRun:
        if not ai.is_enabled():
            raise ai.AIDisabled("Set ANTHROPIC_API_KEY in .env to enable AI analysis.")
        with session_scope() as session:
            est = ai.estimate(session, resolve_scope(session, scope))
            run = AiRun(scope=scope, model=ai_model(), estimate_usd=est["cost_usd"], total=est["to_analyze"])
            session.add(run)
            session.commit()
            session.refresh(run)
        self.executor.submit(self._run, run.id)
        return run

    def _run(self, run_id: int) -> None:
        with session_scope() as session:
            run = session.get(AiRun, run_id)
            if run is None:
                return
            try:
                ai.run_analysis(session, run, resolve_scope(session, run.scope))
            except Exception as exc:  # noqa: BLE001
                log.exception("AI run %s failed", run_id)
                run.status, run.error, run.finished_at = "failed", str(exc)[:500], utcnow()
                session.add(run)
                session.commit()

    def recover(self) -> None:
        with session_scope() as session:
            for run in session.exec(select(AiRun).where(AiRun.status.in_(["queued", "running"]))).all():  # type: ignore[attr-defined]
                run.status, run.error, run.finished_at = "failed", "Interrupted by app restart", utcnow()
                session.add(run)
            session.commit()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)


ai_worker = AiWorker()
