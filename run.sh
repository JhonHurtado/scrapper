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
if [[ ! -x "$VENV/bin/python" ]]; then
    warn "Virtual env not found — creating .venv…"
    python3 -m venv "$VENV"
fi
PYTHON="$VENV/bin/python"
UVICORN="$VENV/bin/uvicorn"

# Reinstala dependencias cuando cambia requirements.txt (o si la instalación
# anterior quedó a medias): un .venv viejo no trae los paquetes nuevos.
REQ_STAMP="$VENV/.requirements.sha"
REQ_HASH="$("$PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$ROOT/requirements.txt")"
if [[ ! -f "$REQ_STAMP" || "$(cat "$REQ_STAMP")" != "$REQ_HASH" ]]; then
    warn "Installing Python dependencies…"
    "$PYTHON" -m pip install -q --upgrade pip
    "$PYTHON" -m pip install -q -r "$ROOT/requirements.txt"
    echo "$REQ_HASH" > "$REQ_STAMP"
    ok "Python deps installed."
fi

# ── Navegador (solo para el respaldo de Google Maps) ─────────────────────────
# Se usa el navegador Chromium que ya tengas (Brave, Chrome, Edge…); no se
# descarga nada. Elige otro con SCRAPER_BROWSER o SCRAPER_BROWSER_PATH.
if [[ "${GEOCODER_GOOGLE_FALLBACK:-true}" != "false" ]]; then
    if BROWSER_EXE="$(cd "$ROOT" && "$PYTHON" -m backend.scraper.official.browser 2>/dev/null)" \
            && [[ "$BROWSER_EXE" != "playwright" ]]; then
        ok "Navegador para el respaldo de Google Maps: $BROWSER_EXE"
    else
        warn "No se encontró Brave, Chrome ni Edge: el respaldo de Google Maps no estará disponible."
        warn "El scraping de fuentes oficiales funciona igual. Para activarlo instala Brave o Chrome,"
        warn "o descarga Chromium con: $PYTHON -m playwright install chromium"
    fi
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
