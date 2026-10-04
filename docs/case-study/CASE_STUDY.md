# Ad Spy Engine: case study

## Ready-to-paste Upwork portfolio entry

**Project title** (61/70 characters)

```text
Ad Spy Engine: Meta Ad Library Scraper & Competitor Dashboard
```

**Your role**

```text
QA Engineer with a developer and product engineering background (solo: product design, scraping, backend, frontend, testing)
```

**Project description** (505/600 characters)

```text
Built a local app that scans competitors' public Meta Ad Library pages with Selenium and turns them into a creative playbook. It collects every active ad (copy, dates, placements, creatives), scores likely winners, groups variations, tracks new, stopped and scaled ads on a schedule with Telegram/email alerts, and exports branded PDF reports with optional Claude AI insights. FastAPI + React dashboard with live progress. Measured: 500 ads in under 3 minutes (172 ads/min), 100% processed without errors.
```

**Skills** (5 tags)

```text
Selenium · Python · Web Scraping · FastAPI · React
```

**Images:** upload `export/upwork-thumbnail.png` as the cover, then `export/slide-02.png` …
`slide-09.png`. All are 1600×1200 (4:3).

---

## The challenge

Marketers and agencies study competitors' Meta ads in the public
[Ad Library](https://www.facebook.com/ads/library/). It shows every active ad, but it's built for
transparency, not strategy:

- **Hours of scrolling.** Researching one brand means opening hundreds of ads, copying text,
  noting start dates and placements, and saving screenshots by hand.
- **No signal.** The library shows no spend or results, so telling a proven winner from a one-day
  test takes judgement every time.
- **No memory.** Competitors launch, scale and kill ads every week. Without history, nobody
  notices the pattern.

Meta's official Ad Library API mainly covers political/social-issue ads and ads delivered in
the EU, so it doesn't solve this for ordinary commercial ads.

## The solution

A local app that scans a competitor's public Meta ads in minutes, scores which ones are winning,
tracks every change, and turns it into a branded client report.

- **One-click scans:** brand name or Page ID in, every active ad out, with live progress.
- **Winner Score:** a transparent 0–100 score from longevity, variations, placements and status.
  Each score shows its own breakdown.
- **Watch & alert:** scheduled re-scans detect new, stopped and scaled ads and send Telegram or
  email alerts.
- **Agency tools:** client folders, side-by-side comparison of 2–3 brands, swipe files with notes
  and tags, and white-label PDF reports with AI-written opportunities.

## Process

1. **Search.** Brand or Page ID, with country, format, placement and status filters.
2. **Scan.** A single Selenium worker drives headless Chrome through the public Ad Library. It
   reads the structured JSON the page already loads (including GraphQL pagination), with a
   text-anchored DOM parser as fallback. Scrolling is humanized and scans are rate-limited. It
   never logs in, and stops cleanly if Meta shows a login wall or captcha.
3. **Score.** Winner Score, perceptual-hash variation grouping and change detection between scans.
4. **Analyze.** Optional Claude analysis of each ad's hook, angle, emotion and offer (structured
   JSON, cached per ad, cost confirmed first).
5. **Report.** Live dashboard, alerts and branded A4 PDF reports.

The project was built in six phases, each ending with tests, a real run against the live site and
a commit: core engine → API and dashboard → intelligence → monitoring → agency mode → showcase.

## Key features

- Live scan screen over Server-Sent Events: progress ring, counters, thumbnails streaming in, log console
- Results gallery with filters, search, sort, "collapse variations" and bulk actions
- Ad detail panel: creative, full copy, "Why this score", variation group, landing page screenshot, AI notes
- Competitor profiles with launch timelines, format and placement mix, top hooks and angles
- Watchlist schedules, change feed and Telegram/email alerts with a "Send test" button
- Compare screen, client folders, swipe-file boards, and branded reports with a cover, executive
  summary, top winners, charts, change log and "Opportunities for you"
- Demo mode with fictional brands, so the product can be shown without real companies' ads

## Engineering highlights

- **Job queue.** The scan table doubles as the queue. One worker, restart recovery, graceful
  cancel and cleanup of orphaned browsers.
- **JSON-first extraction** with a DOM fallback. Selectors and text anchors live in YAML, so a layout
  change is usually a config edit.
- **Change detection** with safeguards. "Stopped" is only inferred when the scan wasn't cut off by
  its limit and the settings match. Older ads first seen because the previous scan was capped
  are labeled "discovered", not "new".
- **Variation grouping.** Perceptual hashing with banded LSH, plus near-duplicate copy matching.
- **Structured AI.** JSON-schema outputs validated with Pydantic, per-ad caching, a cost estimate
  before each run, and a fallback to data-derived insights if the AI step fails.
- **Quality.** 107 automated tests on fixtures captured from real Ad Library pages, plus ruff,
  black, mypy, ESLint, strict TypeScript and Vitest.

## Tech stack

Python · Selenium 4 · FastAPI · SQLModel/SQLite · Alembic · APScheduler · Jinja2 · imagehash ·
Anthropic Claude API · React 19 · TypeScript · Vite · Tailwind CSS v4 · Radix UI · TanStack Query ·
Recharts · Motion · pytest

## Results

Measured with `scripts/benchmark.py` on two real scans of the public Meta Ad Library (US,
headless Chrome 154, Apple Silicon Mac, home connection). Raw data: `docs/benchmarks.json`.

| Scan | Ads | Time | Ads / minute | Processed without error |
|---|---:|---:|---:|---:|
| Gymshark (cap 300) | 300 | 83 s | 216 | 100% |
| Huel (cap 200) | 200 | 91 s | 132 | 100% |
| **Total** | **500** | **174 s** | **172** | **100%** |

- Library ID, start date, placements, copy, card screenshot and creative were captured for every ad.
- **About 6 hours of manual work becomes under 3 minutes.** *Assumption: 45 seconds per ad to
  open, read, note dates and placements, and save a screenshot. This is our estimate, not a
  measured study.*
- This is a portfolio project, so no client testimonials are claimed.

## Want something like this?

I build custom automations: scrapers, monitoring dashboards, data pipelines and AI workflows.
They are designed to run reliably and are handed over with documentation.

**Md Zarin Tasnim**, QA Engineer · Developer & Product Engineering background
[Hire me on Upwork](https://www.upwork.com/freelancers/~01b847509724f9e1ff) ·
[View the code on GitHub](https://github.com/zarindev/ad-spy-engine)
