#!/usr/bin/env bash
# Start relax (backend + frontend) on macOS / Linux.
# Usage:
#   ./start.sh           # install deps if needed, run locally
#   ./start.sh --docker  # build & run with Docker Compose
#   ./start.sh --setup   # install deps only, do not start servers

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="local"
SETUP_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --setup) SETUP_ONLY=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./start.sh [--docker] [--setup]

  (default)  Create a Python venv, install backend + frontend deps, start both servers
  --docker   Run with Docker Compose instead (requires Docker)
  --setup    Install dependencies only; do not start servers
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

info() { printf '\n==> %s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

# --- Docker path -------------------------------------------------------------

if [[ "$MODE" == "docker" ]]; then
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop, then retry."
  docker compose version >/dev/null 2>&1 || die "Docker Compose is unavailable. Update Docker Desktop and retry."

  info "Building and starting with Docker Compose…"
  docker compose up --build
  exit $?
fi

# --- Prerequisite checks -----------------------------------------------------

pick_python() {
  local candidate
  for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON="$(pick_python)" || die "Python 3.12+ is required. Install it from https://www.python.org/downloads/ then retry."
command -v npm >/dev/null 2>&1 || die "Node.js 20+ (with npm) is required. Install it from https://nodejs.org/ then retry."

NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)"
if [[ "$NODE_MAJOR" -lt 20 ]]; then
  die "Node.js 20+ is required (found $(node -v)). Upgrade from https://nodejs.org/"
fi

info "Using $($PYTHON --version) and Node $(node -v)"

# --- Backend setup -----------------------------------------------------------

BACKEND_DIR="$ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

need_venv=0
if [[ ! -x "$VENV_PYTHON" ]]; then
  need_venv=1
elif ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
  info "Existing virtualenv is below Python 3.12 — recreating…"
  rm -rf "$VENV_DIR"
  need_venv=1
fi

if [[ "$need_venv" -eq 1 ]]; then
  info "Creating Python virtual environment…"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

info "Installing backend dependencies…"
python -m pip install --upgrade pip >/dev/null
pip install -e "$BACKEND_DIR" >/dev/null

# --- Frontend setup ----------------------------------------------------------

FRONTEND_DIR="$ROOT/frontend"
if [[ ! -f "$FRONTEND_DIR/.env.local" && -f "$FRONTEND_DIR/.env.example" ]]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env.local"
  info "Created frontend/.env.local from .env.example"
fi

info "Installing frontend dependencies…"
(cd "$FRONTEND_DIR" && npm install)

if [[ "$SETUP_ONLY" -eq 1 ]]; then
  info "Setup complete. Run ./start.sh to launch the app."
  exit 0
fi

# --- Start servers -----------------------------------------------------------

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  info "Shutting down…"
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

info "Starting backend on http://localhost:8000 …"
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

info "Starting frontend on http://localhost:3000 …"
(
  cd "$FRONTEND_DIR"
  export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
  exec npm run dev -- --hostname 127.0.0.1 --port 3000
) &
FRONTEND_PID=$!

cat <<EOF

relax is starting.

  App:      http://localhost:3000
  Calc:     http://localhost:3000/calc
  API docs: http://localhost:8000/docs

Press Ctrl+C to stop both servers.
EOF

# Portable wait (macOS ships Bash 3.2 — no wait -n)
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
