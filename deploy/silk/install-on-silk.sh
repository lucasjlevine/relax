#!/usr/bin/env bash
# Run ON Silk from ~/www-root/relax.
#
# 1) FastAPI via systemd --user on 127.0.0.1:18765
# 2) Next via Silk Unit at /*  (rewrites /api → localhost)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"
HOST="${NETID}.w3.uvm.edu"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
API_PORT="${RELAX_API_PORT:-18765}"

echo "==> Repo:      $ROOT"
echo "==> Site root: $SITE_ROOT"
echo "==> API:       127.0.0.1:${API_PORT} (systemd --user)"

mkdir -p "$SITE_ROOT/public" "$HOME/venvs" "$UNIT_DIR"

# --- Python venv + FastAPI ---
if [[ ! -d "$VENV" ]]; then
  echo "==> Creating venv $VENV"
  python3 -m venv "$VENV"
fi
echo "==> pip install backend"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install "$ROOT/backend"
"$VENV/bin/python" -c "import duckdb, fastapi, uvicorn; print('ok', duckdb.__version__)"
mkdir -p "$ROOT/backend/data/uploads" "$ROOT/backend/data/user_datasets"

echo "==> Install systemd user unit"
cp "$ROOT/deploy/silk/systemd/relax-api.service" "$UNIT_DIR/relax-api.service"
# Allow edits to port via env file if present
systemctl --user daemon-reload
systemctl --user enable relax-api.service
systemctl --user restart relax-api.service
sleep 1
systemctl --user --no-pager --full status relax-api.service || true

echo "==> Probe localhost API"
if curl -fsS "http://127.0.0.1:${API_PORT}/api/health"; then
  echo
else
  echo "error: uvicorn not answering on 127.0.0.1:${API_PORT}" >&2
  echo "  journalctl --user -u relax-api -n 50 --no-pager" >&2
  exit 1
fi

# --- Next build + Silk Unit ---
echo "==> Build Next (proxies /api → 127.0.0.1:${API_PORT})"
RELAX_API_UPSTREAM="http://127.0.0.1:${API_PORT}" "$ROOT/deploy/silk/build-web.sh"
chmod u+x "$ROOT/deploy/silk/dist/web/server.js"

echo "==> Install .silk.ini (Node only — no Python Unit app)"
cp "$ROOT/deploy/silk/.silk.ini" "$SITE_ROOT/.silk.ini"

echo "==> Kill stale Unit Python/Node workers, then load Next"
FORCE=1 "$ROOT/deploy/silk/kill-stale-apps.sh" || true
silk site "${HOST}" update || true
silk app "${HOST}" load

cat <<EOF

Done.

  App:     https://${HOST}/calc
  API:     https://${HOST}/api/health   (via Next → 127.0.0.1:${API_PORT})
  Direct:  curl -sS http://127.0.0.1:${API_PORT}/api/health

systemd:
  systemctl --user status relax-api
  journalctl --user -u relax-api -f

If the user service dies after logout:
  loginctl enable-linger ${NETID}
EOF
