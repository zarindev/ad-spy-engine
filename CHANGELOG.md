# Changelog

All notable changes to Ad Spy Engine are documented here. Format: [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-10-04

### Phase 6: Showcase package
- `scripts/seed_demo.py`: fictional demo dataset (Lumen Skincare, Dewdrop Labs, Northpeak Outdoor,
  Brewlab Coffee) with generated creatives, logos and landing pages, plus three dated scans per brand
  so the change log has real new, stopped and scaled events. It also seeds client folders, swipe files,
  watchlist schedules, demo branding and two sample reports built by the real report builder.
- Demo mode (`run.py --demo`): "Demo data" badge in the top bar. Live scans, AI runs, schedules,
  landing captures and clearing data are refused with a clear message. Demo mode now loads the
  demo folder's own settings (it previously read the real settings first).
- `scripts/benchmark.py`: runs real scans and writes `docs/benchmarks.json` (ads/min, success
  rate, field coverage, environment, and a manual-time estimate with its assumption stated).
- `scripts/capture_screenshots.py`: 12 screens × light/dark at 1440×900 from a demo server.
- `docs/assets/banner.svg`, `logo.svg`, full README, `docs/LEGAL.md`.
- Case study: `docs/case-study/case-study.html` (9 slides at 1600×1200), `CASE_STUDY.md` with a
  ready-to-paste Upwork entry, `scripts/export_case_study.py` → PDF + PNG slides + thumbnail.
- Settings → Danger zone: clear all scans, ads, competitors, clients, boards, reports and files
  (typed confirmation; settings and logo kept).
- Fix: worker thread pools are recreated when the app restarts in the same process.

### Phase 5 — Agency mode & reports
- Client folders: group competitors under a client name (create, rename, notes, delete keeps the
  competitors), move brands between folders, rename competitors.
- Compare screen for 2–3 brands: scoreboard with a marked leader per metric, measured highlights,
  data-derived opportunities, format / winners' format / placement / longevity / CTA / AI hook
  mix, weekly launch cadence and each brand's best ads. Shareable URL (`/compare?ids=…`).
- Swipe files: boards with descriptions and an optional client, save ads from any card, the ad
  detail panel or a bulk selection, per-ad notes and tags (filter by tag), CSV export.
- Branded reports for a client folder, 1–3 competitors or a single scan: cover page (logo, agency,
  "Prepared for"), executive summary, top winners with creatives, format/placement/CTA/angle
  charts, launch cadence, change log, "Opportunities for you" and an optional appendix. A4 PDF
  with page numbers via Chrome's `Page.printToPDF` and CSS `@page` rules.
- "Opportunities for you": written by Claude from the report's measured data when
  `ANTHROPIC_API_KEY` is set (structured output, cost recorded on the report). Otherwise, or if
  the AI step fails, rule-based opportunities built from the same numbers, each with its evidence.
- Brand's-own-ads filter for Compare and reports: keyword scans also return other advertisers
  that mention a brand; those are excluded by default (toggleable).
- Branding in Settings: logo upload (PNG/JPG/WebP/SVG, 2 MB), agency name, colors, live cover
  preview. Colors are validated; the logo path can only be set through the upload endpoint.
- Responsive app shell: below 768px the sidebar becomes a drawer, and grids no longer overflow
  on phones.
- Keyword competitors adopt the casing of a page name that contains the query
  ("athletic greens" → "Athletic Greens").
- Migration 0005 (`client`, `board`, `boarditem`, `competitor.client_id`).

### Phase 4 — Monitoring
- Watchlist: daily or weekly re-scans per competitor at a local time, run by APScheduler while the
  app is open. Runs missed while the app was closed catch up once on start. "Run now",
  pause/resume and per-item alert toggles.
- Change detection after every completed scan, against the previous comparable scan: new,
  stopped, scaled (variation count up) and still running. Stopped ads are only inferred when the
  scan wasn't cut off by its limit and the settings match. Older ads first seen because the
  previous scan hit its limit are reported as "discovered", not new. Stopped ads are marked
  inactive and re-scored.
- Change feed (Watchlist, Competitor profile, Dashboard) with new/stopped/scaled filters;
  "Changes since last scan" on each scan.
- Alerts for scheduled scans via Telegram Bot API and/or SMTP email: summary + top changed ads,
  and also when a scan is blocked or fails. "Send test" buttons in Settings.
- Migration 0004 (`watchlistitem`, `changeevent`, `scan.trigger`, `scan.change_summary`).

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
