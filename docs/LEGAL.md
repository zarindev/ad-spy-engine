# Responsible use

Ad Spy Engine is a research tool for marketers. It reads the **public** Meta Ad Library web
interface (https://www.facebook.com/ads/library/) on your own computer, the same pages anyone can
open in a browser without an account. This page explains what it does, what it deliberately
doesn't do, and what you are responsible for. It is not legal advice.

## What the tool does

- Opens the public Ad Library in Chrome, searches for a brand or Page ID, and scrolls the results
  like a person would.
- Reads the data that page already shows: ad copy, start date, placements, creatives, Library ID.
- Stores it in a local SQLite database under `data/`. Nothing is uploaded anywhere except the
  optional AI step below.

## What it deliberately does not do

- **No login.** It never signs in to Facebook or Instagram and never uses your account or cookies.
- **No captcha or checkpoint bypass.** If Meta shows a login wall, checkpoint or captcha, the
  scan stops with status `blocked` and tells you why. It does not try to get around it.
- **No hidden or private data.** Only what the public Ad Library page displays.
- **No high-volume crawling.** Scans are queued one at a time, with randomized delays between
  scrolls and a minimum gap between scans (`min_seconds_between_scans`, default 45 s).

## Why not the official API?

Meta's [Ad Library API](https://www.facebook.com/ads/library/api/) mainly covers ads about social
issues, elections or politics, plus ads delivered in the EU and UK. Ordinary commercial ads
shown elsewhere are visible in the public Ad Library website but generally not available through
the API. That is why this tool reads the public web interface.

## Your responsibilities

- **Meta's terms.** Meta's Terms of Service restrict automated data collection from its products.
  Read [Meta's Terms](https://www.facebook.com/terms.php) and decide whether your use is
  appropriate. Keep volumes low and use the tool for your own research.
- **Creatives are copyrighted.** Downloaded images and videos belong to the advertisers. Use them
  for internal analysis and swipe files. Don't republish them or pass them off as your own work.
- **Personal data.** Ads can include names and faces of people (creators, customers). If you are
  subject to GDPR or similar laws, treat stored creatives and copy as personal data. Keep them
  only as long as needed and use **Settings → Danger zone** to delete everything.
- **AI analysis (optional).** If you set `ANTHROPIC_API_KEY`, ad copy (and, for report
  opportunities, aggregated statistics and top-ad copy) is sent to Anthropic's API. Nothing is
  sent without a key, and you confirm the estimated cost before each analysis run.
- **Winner Score is a heuristic.** It's inferred from public signals (how long an ad runs,
  variations, placements, status). It isn't spend, reach or conversion data, and reports say so.

## Demo data

The demo dataset (`scripts/seed_demo.py`, `--demo`) uses invented brands and generated
creatives. It contains no real company's ads. Live scans and AI runs are disabled in demo mode.

## Security

The server binds to `127.0.0.1` by default and only serves `data/media` and `data/reports`.
Secrets live in `.env`, which is git-ignored.
