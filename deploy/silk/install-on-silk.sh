#!/usr/bin/env bash
# Run ON Silk from ~/www-root/relax.
#
# 1) FastAPI via systemd --user on 127.0.0.1:8000
# 2) Next via Silk Unit at /*  (rewrites /api → localhost:8000)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"
HOST="${NETID}.w3.uvm.edu"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
API_PORT="${RELAX_API_PORT:-8000}"

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

echo "==> Write systemd user unit (absolute paths, port ${API_PORT})"
cat >"$UNIT_DIR/relax-api.service" <<EOF
[Unit]
Description=relax FastAPI (localhost :${API_PORT})
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT}/backend
Environment=DATASETS_PATH=data/local_groups
Environment=UPLOAD_DIR=data/uploads
Environment=USER_DATASETS_DIR=data/user_datasets
Environment=API_ROOT_PATH=/api
Environment=CORS_ORIGINS=["https://${HOST}"]
ExecStart=${VENV}/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --proxy-headers
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
# Keep a copy in the repo template in sync for humans
cp "$UNIT_DIR/relax-api.service" "$ROOT/deploy/silk/systemd/relax-api.service" 2>/dev/null || true

systemctl --user daemon-reload
systemctl --user enable relax-api.service
systemctl --user restart relax-api.service || true
sleep 2
systemctl --user --no-pager --full status relax-api.service || true

echo "==> Probe localhost API"
if curl -fsS "http://127.0.0.1:${API_PORT}/api/health"; then
  echo
else
  echo "error: uvicorn not answering on 127.0.0.1:${API_PORT}" >&2
  echo "==> journalctl --user -u relax-api:" >&2
  journalctl --user -u relax-api -n 80 --no-pager >&2 || true
  echo "==> Trying uvicorn manually (no systemd)…" >&2
  (
    cd "${ROOT}/backend"
    "${VENV}/bin/uvicorn" app.main:app --host 127.0.0.1 --port "${API_PORT}" --proxy-headers
  ) &
  UV_PID=$!
  sleep 2
  if curl -fsS "http://127.0.0.1:${API_PORT}/api/health"; then
    echo
    echo "uvicorn works manually (pid $UV_PID) — systemd --user failed to keep it up." >&2
    echo "Run:  loginctl enable-linger ${NETID}" >&2
    echo "Then: systemctl --user restart relax-api" >&2
    kill "$UV_PID" 2>/dev/null || true
    wait "$UV_PID" 2>/dev/null || true
    # Continue install; user can fix linger / leave manual process for now
  else
    kill "$UV_PID" 2>/dev/null || true
    wait "$UV_PID" 2>/dev/null || true
    echo "Manual uvicorn also failed. From ${ROOT}/backend run:" >&2
    echo "  ${VENV}/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}" >&2
    exit 1
  fi
fi

# --- Next build + Silk Unit ---
echo "==> Build Next (proxies /api → 127.0.0.1:${API_PORT})"
RELAX_API_UPSTREAM="http://127.0.0.1:${API_PORT}" "$ROOT/deploy/silk/build-web.sh"
chmod u+x "$ROOT/deploy/silk/dist/web/server.js"

echo "==> Install .silk.ini (Node only — no Python Unit app)"
cp "$ROOT/deploy/silk/.silk.ini" "$SITE_ROOT/.silk.ini"

echo "==> Kill stale Unit workers, then load Next"
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
