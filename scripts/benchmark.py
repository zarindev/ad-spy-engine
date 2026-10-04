"""Run real scans and record their numbers in docs/benchmarks.json.

The README and case study quote these numbers, so they must come from genuine scans of the public
Meta Ad Library. Nothing here is estimated except the clearly labeled "manual research"
comparison, whose assumption is written into the file.

    python scripts/benchmark.py                      # Gymshark (300) + Huel (200), US
    python scripts/benchmark.py --brand Nike:200     # custom brand:max_ads pairs
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlmodel import select  # noqa: E402

from app.db.models import Ad, AdSnapshot, Scan  # noqa: E402
from app.db.session import run_migrations, session_scope  # noqa: E402
from app.jobs.runner import create_scan, run_scan  # noqa: E402
from app.scraper.ad_library import ScanParams  # noqa: E402

# Stated assumption for the "time saved" comparison (shown next to the number wherever it's used).
MANUAL_SECONDS_PER_AD = 45  # open the ad, read the copy, note dates/placements, save a screenshot


def chrome_version() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome",
        "chrome",
    ]
    for exe in candidates:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
            if out.returncode == 0:
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def measure(scan_id: int) -> dict:
    with session_scope() as session:
        scan = session.get(Scan, scan_id)
        assert scan is not None
        ads = session.exec(
            select(Ad).join(AdSnapshot, AdSnapshot.ad_id == Ad.id).where(AdSnapshot.scan_id == scan_id)
        ).all()
    n = len(ads)
    duration = scan.duration_seconds or 0

    def share(pred) -> float:  # noqa: ANN001
        return round(100 * sum(1 for a in ads if pred(a)) / n, 1) if n else 0.0

    attempted = scan.ads_processed + scan.ads_failed
    return {
        "brand": scan.query,
        "scan_id": scan.id,
        "status": scan.status,
        "country": scan.country,
        "max_ads": scan.max_ads,
        "meta_reported_results": scan.total_results,
        "ads_found": scan.ads_found,
        "ads_processed": scan.ads_processed,
        "ads_failed": scan.ads_failed,
        "duration_seconds": round(duration, 1),
        "ads_per_minute": round(scan.ads_found / duration * 60, 1) if duration else None,
        "success_rate_pct": round(100 * scan.ads_processed / attempted, 1) if attempted else None,
        "field_coverage_pct": {
            "library_id": share(lambda a: bool(a.library_id)),
            "start_date": share(lambda a: a.start_date is not None),
            "platforms": share(lambda a: bool(a.platforms)),
            "ad_copy_or_headline": share(lambda a: bool(a.ad_copy or a.headline)),
            "card_screenshot": share(lambda a: bool(a.screenshot_path)),
            "creative_downloaded": share(lambda a: bool(a.thumbnail_path or a.media_paths)),
        },
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--brand", action="append", help="brand:max_ads (repeatable)")
    ap.add_argument("--country", default="US")
    ap.add_argument("--out", default=str(ROOT / "docs" / "benchmarks.json"))
    args = ap.parse_args()
    brands = args.brand or ["Gymshark:300", "Huel:200"]

    run_migrations()
    results = []
    for item in brands:
        name, _, limit = item.partition(":")
        params = ScanParams(query=name, country=args.country, max_ads=int(limit or 200), exact_page=True)
        scan = create_scan(params, competitor_name=name)
        print(f"Scanning {name} (max {params.max_ads}) as scan #{scan.id}…", flush=True)
        run_scan(scan.id)
        result = measure(scan.id)
        print(json.dumps(result, indent=1), flush=True)
        results.append(result)

    ok = [r for r in results if r["status"] == "completed" and r["ads_found"]]
    total_ads = sum(r["ads_found"] for r in ok)
    total_seconds = sum(r["duration_seconds"] for r in ok)
    attempted = sum(r["ads_processed"] + r["ads_failed"] for r in ok)
    summary = {
        "scans": len(results),
        "scans_completed": len(ok),
        "total_ads": total_ads,
        "total_seconds": round(total_seconds, 1),
        "ads_per_minute": round(total_ads / total_seconds * 60, 1) if total_seconds else None,
        "success_rate_pct": (
            round(100 * sum(r["ads_processed"] for r in ok) / attempted, 1) if attempted else None
        ),
        "manual_research_estimate": {
            "assumption_seconds_per_ad": MANUAL_SECONDS_PER_AD,
            "assumption": "A person opening each ad in the Ad Library, reading it, noting dates and "
            "placements and saving a screenshot. Our estimate, not a measured study.",
            "manual_minutes": round(total_ads * MANUAL_SECONDS_PER_AD / 60, 1),
            "tool_minutes": round(total_seconds / 60, 1),
        },
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": "Real scans of the public Meta Ad Library recorded by scripts/benchmark.py. "
        "Speeds depend on network, machine and Meta's page; re-run to refresh.",
        "environment": {
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python": platform.python_version(),
            "chrome": chrome_version(),
            "headless": True,
        },
        "summary": summary,
        "scans": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
