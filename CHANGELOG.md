# Changelog

All notable changes to Ad Spy Engine are documented here. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
