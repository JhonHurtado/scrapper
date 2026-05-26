#!/usr/bin/env bash
# run.sh — Starts the Colombia Tourist Scraper (backend + frontend)
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[run.sh]${NC} $*"; }
ok()   { echo -e "${GREEN}[run.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[run.sh]${NC} $*"; }

# ── Cleanup on exit ──────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
    echo ""
    log "Shutting down…"
    [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    ok "Done."
}
trap cleanup EXIT INT TERM

# ── Python venv ──────────────────────────────────────────────────────────────
VENV="$ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
    warn "Virtual env not found — creating .venv and installing dependencies…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"
    ok "Python deps installed."
fi
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

# ── Playwright browsers ──────────────────────────────────────────────────────
if [[ ! -d "$HOME/.cache/ms-playwright" && ! -d "$HOME/Library/Caches/ms-playwright" ]]; then
    warn "Playwright browsers not found — installing Chromium (takes ~1 min)…"
    "$PYTHON" -m playwright install chromium
    ok "Chromium installed."
fi

# ── Node deps ────────────────────────────────────────────────────────────────
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    warn "node_modules not found — running npm install…"
    (cd "$ROOT/frontend" && npm install --silent)
    ok "Node deps installed."
fi

# ── Start backend ────────────────────────────────────────────────────────────
log "Starting FastAPI backend on http://localhost:8000 …"
cd "$ROOT"
"$UVICORN" backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── Start frontend ───────────────────────────────────────────────────────────
log "Starting React frontend on http://localhost:5173 …"
cd "$ROOT/frontend"
npm run dev -- --open &
FRONTEND_PID=$!

# ── Wait ─────────────────────────────────────────────────────────────────────
ok "Both services running. Press Ctrl+C to stop."
wait
