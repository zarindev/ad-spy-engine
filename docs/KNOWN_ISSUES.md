# Known issues & limitations

Meta changes the Ad Library frequently. This file records what could not be fully verified and
how the app degrades. Last verified against the live site: **2026-10-04** (country US, English UI).

## Scraping

| Area | Status | Fallback / notes |
|---|---|---|
| Primary data source | Structured JSON embedded in the page and returned by `/api/graphql/` pagination | If Meta stops shipping these, every ad is still parsed from the DOM (`source = dom`) with a warning per ad in the scan log. |
| Platform icons (DOM fallback only) | Icons are CSS sprite masks with no labels. Facebook's own icon is not a sprite, so it can't be detected from the DOM. | Mapping in `config/selectors.yaml → platform_sprites` is best-effort and sprite offsets change on Meta deploys. Platforms from JSON are exact. |
| Placements | Meta now lists up to 6 placements (adds Threads, WhatsApp). | Winner Score platform ratio is `min(n / 4, 1.0)` so the spec's 4-platform scale still tops out at 100%. |
| Localized UI | Anchors cover EN/ES/FR/DE/PT text, but only English was tested live. | The scraper forces `--lang=en-US`; JSON dates are timestamps and locale-independent. |
| Carousel filter | The Ad Library has no carousel media filter. | `--media carousel` searches all media and keeps only ads parsed as carousel. |
| Collated ads | "N ads use this creative and text" groups render as one card; only the representative ad is returned. | The group size is stored as `variation_count`. Other ads in the group aren't stored separately. |
| Dynamic product ads (DPA) | Copy may contain unrendered placeholders such as `{{product.name}}`. | Parser falls back to the first card's text when the top-level text is a template. |
| Media URLs | fbcdn URLs are signed and expire (`oe=` parameter). | Thumbnails/images are downloaded during the scan. Videos are only downloaded if `download_videos: true`. |
| Login wall / captcha | Not bypassed, by design. | Scan stops with status `blocked` plus suggestions (wait, visible mode, undetected driver, slower pacing). The `blocked` path is verified only against synthetic markers, since the live site didn't block during testing. |
| Meta's result count | The "~N results" figure is Meta's own estimate and can be far higher than the ads it actually returns (e.g. ~13 reported, 3 returned with `has_next_page: false`). | Shown in the UI as "Meta's estimate"; the scan stops when Meta reports no further pages. |
| Catalog placeholders inside copy | Some catalog ads ship text like "Represent the {{product.custom_label_1}} today!". | Fields made only of placeholders fall back to card text or are blanked. Placeholders inside real sentences are kept, since they are the advertiser's actual template. |
| Network drop mid-scan | Page loads retry with backoff. A drop while scrolling looks like "no new ads", so the scan ends as `completed` with partial results. | Re-run the scan; already-stored ads are updated, not duplicated. |
| Hard crash (kill -9 / power loss) | The browser can't be closed by a killed process. | Orphaned chromedriver/Chrome processes are killed on next start (`data/run/drivers.json`), and the scan is marked `interrupted`. |
| Keyword search breadth | Keyword search matches ad text, so it includes affiliates, resellers and unrelated pages. | Use `--exact-page` to keep only matching page names, or scan by Page ID for precision. |

## Intelligence

| Area | Status | Notes |
|---|---|---|
| AI analysis | Built against the official Anthropic SDK (1.11) and tested with a mocked client. **Not yet run against the live API** in development (no key was available). | First real run: analyze a handful of ads and check `Actual cost` in the dialog against the estimate. |
| AI cost estimate | Character-count heuristic (~3.2 chars/token, ~320 output tokens per ad). | Actual input/output tokens and cost are recorded per run from `response.usage`. |
| Variation grouping | Heuristic. Copy matching can chain groups together (A≈B, B≈C), so resellers posting one caption over many images form one large group. | Thresholds live in `analysis/grouping.py` (`PHASH_DISTANCE`, `COPY_SIMILARITY`). Video ads are grouped by their preview frame. |
| Landing pages | Viewport screenshot (1366×900) after dismissing common cookie banners. Sites with bot protection may show a challenge page. | Failures are stored with the error and can be retried from Ad Detail. Pages are reused for 7 days. |

## Monitoring

| Area | Status | Notes |
|---|---|---|
| Scheduler | Runs only while the app is open. A missed run executes once on the next start. | Times are the computer's local time zone. For unattended monitoring, keep the app running (e.g. start it at login). |
| Stopped detection | Needs the current scan to cover all of the competitor's ads. | If a scan stops at its max-ads limit, stopped ads aren't inferred and the summary says why. Set the watchlist's max ads above the competitor's ad count. |
| Telegram / email | Tested against mocked transports (request format, auth, STARTTLS, error messages). | Use **Settings → Send test** after adding credentials to `.env`. Gmail needs an app password; port 465 uses implicit TLS, other ports use STARTTLS. |

## Agency mode & reports

| Area | Status | Notes |
|---|---|---|
| Brand's own ads | Matches ads whose page name contains the competitor name (or the competitor's Page ID). | Sub-brands with different names (e.g. "AG1" for "Athletic Greens") are kept only if the name appears in the page name. If nothing matches, all ads are kept. Toggle off to include everything. |
| AI opportunities | Verified against a mocked client (request shape, structured output, fallback to data-derived opportunities on any error). Not yet run against the live API in this build. | Cost is recorded on each report (`options.ai_usage`). The model only receives measured numbers and top ads, and is told not to invent spend or performance figures. |
| PDF | Chrome print engine; page numbers use CSS `@page` margin boxes (Chrome 131+). | Older Chrome versions render the PDF without the footer. Fonts load from Google Fonts. Offline, the PDF falls back to system fonts. |
| Report size | Creatives are embedded as data URIs so the HTML is a single file. | A 30-winner report with large screenshots can reach 10–20 MB. Lower "Top winners to feature" for email. |

## Platform & showcase

| Area | Status | Notes |
|---|---|---|
| Windows | Developed and tested on macOS. Paths use `pathlib`, `.bat` files are CRLF, and Chrome is found by Selenium Manager. | `setup.bat` / `start.bat` have not yet been run on a fresh Windows machine. Run them once and report any error output. |
| Benchmarks | `docs/benchmarks.json` comes from two real scans on one Mac and one home connection. | Speeds vary with network, machine and Meta's page. Re-run `scripts/benchmark.py` to refresh. The "manual time" figure is an estimate with its assumption written next to it. |
| Demo mode | Fictional data; live actions are disabled. | The demo's scan durations reuse the measured ads/min so the dashboard's throughput looks realistic. They aren't separate measurements. |
| Demo GIF | Not included (can't be recorded headlessly in a meaningful way). | See the HTML comment in README.md for what to record. |

## Storage

Each ad stores a PNG card screenshot (~60–150 KB) plus up to `max_media_per_ad` original images.
Expect roughly 0.5 MB per ad. Lower `max_media_per_ad`, or set `download_media: false`.
