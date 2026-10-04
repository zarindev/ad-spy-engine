# Changelog

All notable changes to Ad Spy Engine are documented here. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Phase 3 — Intelligence
- Variation grouping: perceptual hashing (pHash, banded LSH) plus normalized/near-identical copy
  matching groups each competitor's ads into "N creatives · M copy tests". Runs automatically
  after every scan; "Collapse variations" in the gallery; groups on Ad Detail and Competitor pages.
- Landing page capture: top distinct destinations (tracking parameters stripped, on-platform links
  skipped) are screenshotted after each scan; on-demand capture from Ad Detail.
- AI copy analysis (optional, `ANTHROPIC_API_KEY`): batched structured-output calls to Claude
  (default `claude-sonnet-5-5`, configurable). Returns hook type, hook, angle, emotion, offer, CTA,
  audience, summary and "what to steal". Results are cached per Library ID. Cost estimate and
  explicit confirm come before every run, and actual tokens and cost are recorded per run.
  Server-side refusal fallback is enabled.
- Competitors list and Competitor Profile: KPIs, weekly launch/running timeline, format,
  placement, CTA and lifespan breakdowns, variation groups, AI hooks & angles, ideas worth
  stealing, top ads.
- Migration 0003 (grouping columns, `landingpage`, `adanalysis`, `airun`).

### Phase 2 — API + Dashboard
- FastAPI app with routers for scans, ads, competitors, stats, reports, settings and SSE events;
  OpenAPI docs at `/api/docs`.
- Background scan worker (single thread, `scan` table as the queue), restart recovery
  (`interrupted` / re-queue), graceful shutdown, orphaned-browser cleanup.
- Live progress over Server-Sent Events, including scan-thread log lines.
- React + TypeScript dashboard: Dashboard, New Scan, Live Scan, Scan History, Results Gallery
  (masonry/list, filters, infinite scroll, bulk export), Ad Detail slide-over with "Why this
  score", Reports (wizard, in-app preview, PDF), Settings; ⌘/Ctrl+K command palette;
  dark/light themes.
- CSV export (per scan, filtered, or selected ads), HTML + PDF reports via headless Chrome.
- `setup.bat`/`start.bat`/`dev.bat` and `.sh` equivalents.
- Parser: placeholder-only catalog text is never shown; `cli.py reparse` rebuilds ads from stored JSON.
- Competitor logos stored locally; keyword competitors adopt the page's own casing.

### Phase 1 — Core engine (CLI)
- Selenium scraper for the public Meta Ad Library: keyword and exact Page ID search, country /
  media / platform / status filters, consent-dialog handling, auto-scroll with humanized pacing.
- Hybrid extraction: structured JSON the page already receives (server-rendered + intercepted
  `/api/graphql/` pagination) merged with a text-anchored DOM parser fallback.
- Per-ad card screenshots (sticky overlays hidden), size-limited media downloads on a thread pool.
- Blocking detection (login wall, checkpoint, captcha flag, error banners) → `blocked` status with suggestions.
- Retries with exponential backoff; a failing ad never stops a scan; cancellation via Ctrl+C.
- SQLite + SQLModel with Alembic migrations; `AdSnapshot` per scan for change tracking.
- Winner Score (0–100) with configurable weights and a "why this score" breakdown.
- `cli.py` with `scan`, `scans`, `ads`, `report`, `rescore`; rich progress + results table.
- Single-file HTML scan report with embedded screenshots.
- 53 offline tests against real captured fixtures; `scripts/capture_fixtures.py` to refresh them.
