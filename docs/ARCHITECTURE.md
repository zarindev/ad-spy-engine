# Architecture

Ad Spy Engine is a local-first app: one Python process serves the API, runs scans on a background
thread, and serves the built React dashboard. Nothing needs Redis, Docker or a cloud account.

```mermaid
flowchart LR
  UI["React dashboard<br/>(Vite build)"] -- REST --> API["FastAPI"]
  UI -- "SSE /api/scans/:id/events" --> API
  API -- enqueue --> Q[("scan table<br/>= job queue")]
  Q --> W["Scan worker thread"]
  W --> S["Selenium + Chrome"]
  S -- "public pages" --> M["Meta Ad Library"]
  S --> P["Parser<br/>JSON + DOM"]
  P --> DB[("SQLite<br/>SQLModel + Alembic")]
  P --> F["data/media<br/>screenshots, images"]
  DB --> SC["Winner Score"]
  W -- events --> B["Event bus"] -- SSE --> UI
  DB --> R["Reports<br/>Jinja2 → HTML → Chrome PDF"]
```

## Request flow of a scan

1. `POST /api/scans` validates the input and creates a `Scan` row (`queued`) plus its `Competitor`.
   It then calls `worker.enqueue()`.
2. `ScanWorker` (a single-thread `ThreadPoolExecutor`) picks the scan up. It enforces the
   `min_seconds_between_scans` rate limit and calls `runner.run_scan()`.
3. `AdLibraryScraper` launches Chrome via `driver.create_driver()`. Before any page script runs, it
   injects a hook (`XHR_CAPTURE_JS`) that keeps a copy of the Ad Library's own `/api/graphql/`
   pagination responses.
4. The scraper opens the search URL, dismisses cookie dialogs, checks for blocking, and reads the
   server-rendered JSON (first page + Meta's estimated total). Then it scrolls with randomized,
   human-like pacing.
5. After each scroll it drains the captured JSON and finds new ad cards in the DOM. Cards are
   located by the "Library ID" text anchor, never by CSS classes. For each card it:
   - maps the JSON node → `AdRecord` (`parser.record_from_node`);
   - parses the card HTML → `AdRecord` (`parser.record_from_card_html`) as a fallback;
   - merges the two (JSON wins, DOM fills gaps and supplies `raw_html`);
   - screenshots the card element, with sticky overlays hidden.
6. `runner.on_ad` upserts the `Ad`, writes an `AdSnapshot` for this scan, computes the Winner
   Score, saves the screenshot and queues media downloads on a small thread pool.
7. Events (`status`, `progress`, `ad`, `log`, `blocked`) go to the in-process `EventBus`, which
   fans them out to SSE subscribers. Log lines come from a logging handler bound to the scan thread.

## Why JSON first

The Ad Library page already contains every result as structured JSON. That is the same data its
React UI renders: Library ID, page, start/end timestamps, placements, collation count, creative
URLs, CTA and link. Reading it is more accurate and far more stable than scraping the rendered
DOM, whose class names are obfuscated and change on every Meta deploy. The text-anchored DOM
parser stays as a fallback and is tested against the same fixtures, so a Meta change that removes
the JSON degrades the data but doesn't break scans.

## Reliability

| Failure | Handling |
|---|---|
| Stale element / timeout | `with_retries()` exponential backoff |
| One ad fails to parse | counted in `ads_failed`, logged, scan continues |
| Login wall / checkpoint / captcha flag | `ScanBlocked` → status `blocked` + suggestions; never bypassed |
| Cancel button / Ctrl+C | `threading.Event` checked between ads and during sleeps; browser closed |
| App closed mid-scan | graceful shutdown cancels and marks `interrupted` |
| Hard crash (kill -9, power loss) | startup marks `running` scans `interrupted`, re-queues `queued` ones; counters are saved every 10 ads |
| Orphaned Chrome after a crash | PIDs + profile dirs tracked in `data/run/drivers.json`, killed on next start |

## Intelligence pipeline (after each scan)

1. **Grouping** (`analysis/grouping.py`). Computes a 64-bit pHash of each thumbnail and a hash of
   the normalized copy. Candidate pairs come from 8-band LSH (two hashes within 6 bits always
   share ≥ 2 bands), confirmed by Hamming distance. Copy matches use exact hash plus
   `SequenceMatcher ≥ 0.92` within a first-three-words block. Union-find yields groups; each ad
   stores `group_key`, `group_size`, `group_creatives` and `group_copies`.
2. **Landing pages** (`scraper/landing.py`). Normalizes URLs (drops `utm_*`, `fbclid`, …), skips
   on-platform destinations, and captures the top `landing.max_per_scan` distinct pages by Winner
   Score with a separate headless Chrome.
3. **AI analysis** (`analysis/ai.py`, on demand). `AiWorker` runs batches of `ai.batch_size` ads
   per `messages.create` call with `output_config.format` (JSON schema) and `effort: low`. Each
   batch is validated with Pydantic and stored in `adanalysis`, keyed by Library ID, so an ad is
   never paid for twice. A failing batch is counted and skipped; the run continues.

## Monitoring

- `jobs/scheduler.py`: an APScheduler `BackgroundScheduler` in the local time zone, with one cron
  job per enabled `WatchlistItem` (re-synced whenever the watchlist changes). A run creates a
  normal scan with `trigger="schedule"` and enqueues it on the same scan worker, so rate limits
  and one-at-a-time still apply. On startup, items whose `next_run_at` passed while the app was
  closed are run once.
- `analysis/changes.py` runs after every completed scan. It compares `AdSnapshot` sets with the
  previous comparable scan, writes `ChangeEvent` rows (`new`, `stopped`, `scaled`), and stores a
  summary on the scan.
- `notify/`: after a scheduled scan finishes with changes (or is blocked or fails), the worker
  sends one alert to each configured channel. A failing channel never blocks the other.

## Agency mode & reports

- `analysis/insights.py` holds the brand-level numbers shared by Compare and reports: format,
  placement, CTA and longevity mix, winner rate, launch cadence, variation groups. It also
  builds templated highlights and rule-based opportunities, each sentence citing the numbers it
  came from. `is_own_ad` keeps a brand's own pages, because keyword scans also return other
  advertisers that mention it.
- `reports/builder.py` turns a `ReportSpec` (competitors, optional scan, client name, sections,
  top N, AI on/off) into one self-contained HTML file from `templates/brand_report.html.j2`. With AI
  enabled, `ai.strategy_brief` sends the measured data and top ads to Claude with a JSON schema
  and returns an executive summary and 3–5 opportunities. Any failure falls back to the
  rule-based opportunities and is recorded on the report.
- `reports/pdf.py` prints the HTML with headless Chrome's DevTools `Page.printToPDF`
  (`preferCSSPageSize`), so the template's `@page` rules control A4 size, margins, the
  margin-free cover and "Page X of Y" footers.
- Clients (`client`, `competitor.client_id`) and swipe files (`board`, `boarditem` with note and
  tags) are plain CRUD routers (`api/clients.py`, `api/boards.py`).

## Data model

- `competitor`: one tracked brand (name, optional Page ID, local logo).
- `scan`: one run (filters, status, counters, timing, log path). Doubles as the job queue.
- `ad`: unique by `library_id`; latest parsed values, score + breakdown, local media paths, and
  zlib-compressed `raw_json`/`raw_html` so ads can be re-parsed (`cli.py reparse`) after parser fixes.
- `adsnapshot`: one row per ad per scan. This is the basis for change detection (Phase 4).
- `report`: generated reports (HTML + PDF paths, options).
- `landingpage`: one screenshot per normalized destination URL.
- `watchlistitem` / `changeevent`: schedules and detected changes between scans.
- `adanalysis` / `airun`: cached AI results per Library ID, and per-run token/cost accounting.
- `client`: agency client folders; `competitor.client_id` assigns a brand to one.
- `board` / `boarditem`: swipe files. Each item is a saved ad with a note and tags (unique per board).

Schema changes go through Alembic (`backend/app/db/migrations`). Migrations run automatically at startup.

## Frontend

React 19 + TypeScript + Vite, with Tailwind v4 tokens (dark first) and shadcn-style components on
Radix primitives. TanStack Query handles server state, SSE (`EventSource`) carries live progress,
and Motion handles micro-animations. In production FastAPI serves `frontend/dist`. In development
Vite proxies `/api` and `/files` to `:8000`.

## Demo mode & showcase scripts

`run.py --demo` points `ADSPY_DATA_DIR` at `data-demo/` and sets `ADSPY_DEMO=1`. `core/demo.py`
makes scan, rerun, watchlist-run, AI-run, landing-capture and clear-data endpoints return 403,
the scheduler isn't started, and `/api/health` reports `demo: true` for the UI badge.
`scripts/seed_demo.py` builds that folder through the real code paths (`compute_score`,
`detect_changes`, `regroup_competitor`, the report builder). `scripts/benchmark.py` records real
scans. `scripts/capture_screenshots.py` and `scripts/export_case_study.py` drive headless Chrome.

## Files served

Only `data/media` and `data/reports` are mounted (`/files/media`, `/files/reports`). The database,
logs and settings are never served. The server binds to `127.0.0.1` by default.
