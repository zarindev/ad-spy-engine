#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || ./setup.sh
[ -f frontend/dist/index.html ] || (cd frontend && npm run build)
exec .venv/bin/python backend/run.py "$@"
