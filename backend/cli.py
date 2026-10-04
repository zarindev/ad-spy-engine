"""Ad Spy Engine command line.

Examples:
    python cli.py scan "Gymshark" --country US --max-ads 200
    python cli.py scan 129669023798560 --page-id --media video --visible
    python cli.py scans
    python cli.py ads --scan 3 --limit 20
    python cli.py report 3
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import (
    Console,  # noqa: E402
    Group,  # noqa: E402
)
from rich.live import Live  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.progress import (  # noqa: E402
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402
from sqlmodel import select  # noqa: E402

from app.core.logging import setup_logging  # noqa: E402
from app.db.models import Ad, Competitor, Scan  # noqa: E402
from app.db.session import run_migrations, session_scope  # noqa: E402

console = Console()
BADGE_STYLE = {
    "winner": ("🏆 Winner", "bold #F59E0B"),
    "promising": ("📈 Promising", "green"),
    "testing": ("🧪 Testing", "cyan"),
}
STATUS_STYLE = {
    "completed": "green",
    "blocked": "yellow",
    "failed": "red",
    "cancelled": "magenta",
    "interrupted": "magenta",
    "running": "blue",
    "queued": "dim",
}


def ads_table(ads: list[Ad], title: str) -> Table:
    table = Table(title=title, title_style="bold", header_style="bold #A78BFA", expand=True)
    table.add_column("Score", justify="right", width=5)
    table.add_column("Badge", width=12)
    table.add_column("Page", min_width=10, max_width=22, overflow="ellipsis", no_wrap=True)
    table.add_column("Headline / copy", ratio=1, min_width=16, overflow="ellipsis", no_wrap=True)
    table.add_column("Format", width=9)
    table.add_column("Days", justify="right", width=5)
    table.add_column("Var", justify="right", width=4)
    table.add_column("Platforms", width=12)
    table.add_column("Library ID", style="dim", width=17)
    for ad in ads:
        label, style = BADGE_STYLE.get((ad.score_breakdown or {}).get("badge", "testing"), ("", ""))
        copy = (ad.headline or ad.ad_copy or "—").replace("\n", " ")
        plats = "".join(p[0] for p in ad.platforms or [])  # F I M A T W
        table.add_row(
            str(ad.score),
            Text(label, style=style),
            ad.page_name or "—",
            copy,
            ad.media_type,
            str(ad.days_running),
            str(ad.variation_count),
            plats,
            ad.library_id,
        )
    return table


def cmd_scan(args: argparse.Namespace) -> int:
    from app.jobs.runner import create_scan, run_scan
    from app.reports.builder import build_scan_report
    from app.scraper.ad_library import ScanParams, build_search_url

    params = ScanParams(
        query=args.query,
        search_type="page_id" if args.page_id else "keyword",
        country=args.country,
        media_type=args.media,
        platforms=[p for p in (args.platforms or "").split(",") if p],
        active_status=args.status,
        max_ads=args.max_ads,
        exact_page=args.exact_page,
        headless=not args.visible,
        driver_type=args.driver,
    )
    scan = create_scan(params, competitor_name=args.name)
    console.print(
        Panel.fit(
            f"[bold]{args.query}[/] · {params.search_type} · {params.country} · media={params.media_type} · "
            f"max {params.max_ads} ads · {'visible' if args.visible else 'headless'}\n[dim]{build_search_url(params)}[/]",
            title=f"[bold #A78BFA]Ad Spy Engine[/] — scan #{scan.id}",
            border_style="#6D28D9",
        )
    )

    cancel = threading.Event()
    signal.signal(
        signal.SIGINT,
        lambda *_: (cancel.set(), console.print("[yellow]Cancelling… (finishing current ad)[/]")),
    )

    progress = Progress(
        SpinnerColumn(style="#A78BFA"),
        TextColumn("[bold]{task.description}"),
        BarColumn(complete_style="#6D28D9"),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[extra]}"),
        TimeElapsedColumn(),
        console=console,
    )
    task = progress.add_task("Starting browser", total=params.max_ads, extra="")
    recent: list[str] = []
    state = {"status": "", "blocked": None}

    def on_event(kind: str, data: dict) -> None:
        if kind == "progress":
            target = min(params.max_ads, data.get("total") or params.max_ads)
            progress.update(
                task,
                total=target,
                completed=data.get("found", 0),
                extra=(
                    f"~{data['total']} on Meta · {data['failed']} failed"
                    if data.get("total") is not None
                    else f"{data.get('failed', 0)} failed"
                ),
            )
        elif kind == "status":
            state["status"] = data.get("status", "")
            progress.update(
                task,
                description={
                    "starting_browser": "Starting browser",
                    "loading": "Loading Ad Library",
                    "scrolling": "Collecting ads",
                    "rate_limited": "Rate limited — waiting",
                }.get(state["status"], state["status"].capitalize()),
            )
        elif kind == "ad":
            ad = data["ad"]
            recent.append(
                f"[{'#F59E0B' if ad['badge'] == 'winner' else 'dim'}]{ad['score']:>3}[/] {ad['page_name'] or '—'} · {ad['media_type']} · {ad['days_running']}d"
            )
            del recent[:-4]
        elif kind == "log" and data.get("level") == "warning":
            recent.append(f"[yellow]⚠ {data['message']}[/]")
            del recent[:-4]
        elif kind == "blocked":
            state["blocked"] = data

    started = time.time()
    with Live(Group(progress), console=console, refresh_per_second=8) as live:

        def refresh(kind: str, data: dict) -> None:
            on_event(kind, data)
            live.update(Group(progress, Text.from_markup("\n".join(recent) or " ")))

        scan = run_scan(scan.id, on_event=refresh, cancel=cancel, driver_type=args.driver)
    elapsed = time.time() - started

    with session_scope() as session:
        ads = session.exec(select(Ad).where(Ad.last_scan_id == scan.id).order_by(Ad.score.desc(), Ad.days_running.desc())).all()  # type: ignore[attr-defined]
    if ads:
        console.print(
            ads_table(
                list(ads[: args.show]), f"Top {min(args.show, len(ads))} of {len(ads)} ads by Winner Score"
            )
        )

    style = STATUS_STYLE.get(scan.status, "white")
    rate = (scan.ads_found / elapsed * 60) if elapsed else 0
    summary = (
        f"[{style}]● {scan.status.upper()}[/]  {scan.ads_found} ads · {scan.new_ads} new · {scan.ads_failed} failed · "
        f"{elapsed:.0f}s · {rate:.1f} ads/min"
    )
    if scan.block_reason:
        summary += f"\n[yellow]Blocked:[/] {scan.block_reason}"
        for tip in (state["blocked"] or {}).get("suggestions", []):
            summary += f"\n  • {tip}"
    if scan.error:
        summary += f"\n[red]{scan.error}[/]"
    if scan.ads_found:
        report = build_scan_report(scan.id)
        summary += f"\nReport: [link=file://{report}]{report}[/link]"
    summary += f"\nLog: {scan.log_path}"
    console.print(Panel(summary, border_style=style, title="Scan summary"))
    return 0 if scan.status == "completed" else 1


def cmd_scans(args: argparse.Namespace) -> int:
    with session_scope() as session:
        rows = session.exec(select(Scan, Competitor).join(Competitor).order_by(Scan.id.desc()).limit(args.limit)).all()  # type: ignore[union-attr]
    table = Table(title="Scan history", header_style="bold #A78BFA")
    for col in (
        "ID",
        "Competitor",
        "Query",
        "Type",
        "Country",
        "Status",
        "Ads",
        "New",
        "Failed",
        "Duration",
        "Started",
    ):
        table.add_column(col)
    for scan, comp in rows:
        dur = f"{scan.duration_seconds:.0f}s" if scan.duration_seconds else "—"
        table.add_row(
            str(scan.id),
            comp.name,
            scan.query,
            scan.search_type,
            scan.country,
            Text(scan.status, style=STATUS_STYLE.get(scan.status, "")),
            str(scan.ads_found),
            str(scan.new_ads),
            str(scan.ads_failed),
            dur,
            scan.started_at.strftime("%Y-%m-%d %H:%M") if scan.started_at else "—",
        )
    console.print(table)
    return 0


def cmd_ads(args: argparse.Namespace) -> int:
    with session_scope() as session:
        stmt = select(Ad)
        if args.scan:
            stmt = stmt.where(Ad.last_scan_id == args.scan)
        if args.competitor:
            comp = session.exec(select(Competitor).where(Competitor.name.ilike(f"%{args.competitor}%"))).first()  # type: ignore[attr-defined]
            if not comp:
                console.print(f"[red]No competitor matching {args.competitor!r}[/]")
                return 1
            stmt = stmt.where(Ad.competitor_id == comp.id)
        ads = session.exec(stmt.order_by(Ad.score.desc()).limit(args.limit)).all()  # type: ignore[attr-defined]
    console.print(ads_table(list(ads), f"{len(ads)} ads"))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from app.reports.builder import build_scan_report

    path = build_scan_report(args.scan_id)
    console.print(f"[green]Report written:[/] {path}")
    return 0


def cmd_rescore(_args: argparse.Namespace) -> int:
    from app.analysis.scoring import compute_score

    with session_scope() as session:
        ads = session.exec(select(Ad)).all()
        for ad in ads:
            ad.score, ad.score_breakdown = compute_score(
                ad.days_running, ad.variation_count, ad.platforms, ad.status == "active"
            )
            session.add(ad)
        session.commit()
    console.print(f"[green]Rescored {len(ads)} ads[/]")
    return 0


def cmd_reparse(_args: argparse.Namespace) -> int:
    """Re-run the parser on stored raw JSON (after parser fixes), keeping screenshots/media."""
    import json

    from app.jobs.runner import upsert_ad
    from app.scraper.parser import decompress, record_from_node

    updated = 0
    with session_scope() as session:
        ads = session.exec(select(Ad).where(Ad.raw_json.is_not(None))).all()  # type: ignore[union-attr]
        for ad in ads:
            node = json.loads(decompress(ad.raw_json) or "{}")
            record = record_from_node(node, ad.last_seen_at.date())
            for field in ("ad_copy", "headline", "description", "cta_text"):
                setattr(ad, field, None)  # allow upsert to clear stale values
            session.add(ad)
            session.flush()
            upsert_ad(session, record, ad.competitor_id, ad.last_scan_id or 0) if ad.last_scan_id else None
            updated += 1
        session.commit()
    console.print(f"[green]Re-parsed {updated} ads from stored JSON[/]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py", description="Ad Spy Engine — Meta Ad Library intelligence"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan the Meta Ad Library for a brand or page")
    scan.add_argument("query", help="Brand / keyword, or a Facebook Page ID with --page-id")
    scan.add_argument("--page-id", action="store_true", help="Treat query as an exact Facebook Page ID")
    scan.add_argument("--name", help="Competitor display name (defaults to the query / page name)")
    scan.add_argument("--country", default="US", help="ISO country code or ALL (default US)")
    scan.add_argument(
        "--media",
        default="all",
        choices=["all", "image", "video", "meme", "carousel"],
        help="Media type filter",
    )
    scan.add_argument("--platforms", help="Comma list: facebook,instagram,messenger,audience_network")
    scan.add_argument("--status", default="active", choices=["active", "inactive", "all"])
    scan.add_argument(
        "--max-ads", type=int, default=None, help="Stop after N ads (default from settings.yaml)"
    )
    scan.add_argument(
        "--exact-page",
        action="store_true",
        help="Keyword mode: keep only ads from pages whose name matches the query",
    )
    scan.add_argument("--visible", action="store_true", help="Show the browser window")
    scan.add_argument("--driver", choices=["chrome", "undetected"], help="Override driver type")
    scan.add_argument("--show", type=int, default=15, help="Rows to print in the results table")
    scan.set_defaults(func=cmd_scan)

    scans = sub.add_parser("scans", help="List scan history")
    scans.add_argument("--limit", type=int, default=20)
    scans.set_defaults(func=cmd_scans)

    ads = sub.add_parser("ads", help="List stored ads by score")
    ads.add_argument("--scan", type=int)
    ads.add_argument("--competitor")
    ads.add_argument("--limit", type=int, default=25)
    ads.set_defaults(func=cmd_ads)

    report = sub.add_parser("report", help="Write an HTML report for a scan")
    report.add_argument("scan_id", type=int)
    report.set_defaults(func=cmd_report)

    rescore = sub.add_parser("rescore", help="Recompute Winner Scores after changing weights")
    rescore.set_defaults(func=cmd_rescore)

    reparse = sub.add_parser("reparse", help="Re-run the parser on stored raw JSON (after parser updates)")
    reparse.set_defaults(func=cmd_reparse)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    run_migrations()
    from app.scraper.cleanup import cleanup_orphans

    cleanup_orphans()
    if getattr(args, "max_ads", "unset") is None:
        from app.core.config import get_settings

        args.max_ads = int(get_settings().get("scraping", {}).get("max_ads", 200))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
