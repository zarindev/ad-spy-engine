"""Start the Ad Spy Engine server (used by start.bat / start.sh)."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from app.core.config import env, get_settings

    server = get_settings().get("server", {})
    ap = argparse.ArgumentParser(description="Run Ad Spy Engine")
    ap.add_argument("--host", default=env("ADSPY_HOST") or server.get("host", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(env("ADSPY_PORT") or server.get("port", 8000)))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development)")
    ap.add_argument(
        "--demo", action="store_true", help="Use the demo dataset in data-demo/ (see scripts/seed_demo.py)"
    )
    args = ap.parse_args()

    if args.demo:
        os.environ["ADSPY_DATA_DIR"] = str(Path(__file__).resolve().parents[1] / "data-demo")

    import uvicorn

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    if not args.no_browser and server.get("open_browser", True):
        threading.Thread(target=lambda: (time.sleep(1.8), webbrowser.open(url)), daemon=True).start()
    print(f"\n  Ad Spy Engine → {url}\n  API docs     → {url}/api/docs\n  Press Ctrl+C to stop.\n")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(__file__).resolve().parent / "app")] if args.reload else None,
        app_dir=str(Path(__file__).resolve().parent),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
