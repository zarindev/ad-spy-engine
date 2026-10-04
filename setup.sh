#!/usr/bin/env bash
# Ad Spy Engine — one-time setup for macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")"

ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; exit 1; }

echo
echo "  Ad Spy Engine — one-time setup"
echo

PY=""
for cand in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.11+ not found — install it from https://www.python.org/downloads/"
ok "Python $($PY -c 'import platform; print(platform.python_version())')"

command -v node >/dev/null 2>&1 || fail "Node.js 20+ not found — install the LTS from https://nodejs.org/"
ok "Node $(node -v)"

if [ -d "/Applications/Google Chrome.app" ] || command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1; then
  ok "Google Chrome found"
else
  warn "Google Chrome not found — install it before scanning (https://www.google.com/chrome/)"
fi

[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
ok "Python packages installed"

(cd frontend && npm install --no-fund --no-audit --loglevel=error && npm run build >/dev/null)
ok "Dashboard built"

[ -f .env ] || { cp .env.example .env; ok "Created .env (edit it to add optional API keys)"; }
.venv/bin/python -c "import sys; sys.path.insert(0, 'backend'); from app.db.session import run_migrations; run_migrations()"
ok "Database ready"

echo
echo "  Setup complete. Run ./start.sh to launch Ad Spy Engine."
echo
