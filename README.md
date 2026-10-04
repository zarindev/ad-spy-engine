# Ad Spy Engine

> Turn any competitor's Meta ads into a winning-creative playbook.

Local-first app that scans the public Meta Ad Library with Selenium, scores which ads are likely
winners, and shows everything in a live dashboard with client-ready reports.

*Full showcase README with screenshots and benchmarks arrives in Phase 6.*

## Quick start

Prerequisites: Python 3.11+, Node 20+, Google Chrome.

```bash
# Windows
setup.bat
start.bat

# macOS / Linux
./setup.sh
./start.sh
```

The app opens at http://localhost:8000. API docs: http://localhost:8000/api/docs.

### CLI

```bash
cd backend
../.venv/bin/python cli.py scan "Gymshark" --exact-page --max-ads 200   # Windows: ..\.venv\Scripts\python
../.venv/bin/python cli.py scan 129669023798560 --page-id --media video
../.venv/bin/python cli.py scans
```

### Development

`dev.bat` / `./dev.sh` runs the API with auto-reload on :8000 and Vite with hot reload on :5173.
Tests: `.venv/bin/python -m pytest` and `cd frontend && npm test`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

Public data only — no login, no captcha bypass, rate-limited. MIT licensed.
