#!/usr/bin/env bash
# Development mode: API with auto-reload on :8000 + Vite dev server (hot reload) on :5173.
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/python backend/run.py --reload --no-browser &
API=$!
trap 'kill $API 2>/dev/null' EXIT
cd frontend && npm run dev -- --open
