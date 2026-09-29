#!/usr/bin/env bash
# Run ON Silk from ~/www-root/relax.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"
HOST="${NETID}.w3.uvm.edu"

echo "==> Repo:       $ROOT"
echo "==> Site root:  $SITE_ROOT"

mkdir -p "$SITE_ROOT/public" "$HOME/venvs"

echo "==> Building Next (basePath=/relax) → deploy/silk/dist/web"
"$ROOT/deploy/silk/build-web.sh"

if [[ ! -f "$ROOT/deploy/silk/dist/web/server.js" ]]; then
  echo "error: missing dist/web/server.js" >&2
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  echo "==> Creating venv at $VENV"
  python3 -m venv "$VENV"
fi

echo "==> pip install backend"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install "$ROOT/backend"

chmod u+x "$ROOT/backend/wsgi.py" "$ROOT/deploy/silk/dist/web/server.js"
mkdir -p "$ROOT/backend/data/uploads" "$ROOT/backend/data/user_datasets"

INI_DST="$SITE_ROOT/.silk.ini"
cp "$ROOT/deploy/silk/.silk.ini" "$INI_DST"
ABS_VENV="$(readlink -f "$VENV" 2>/dev/null || realpath "$VENV")"
tmp="$(mktemp)"
sed "s|^venv-path = .*|venv-path = ${ABS_VENV}|" "$INI_DST" >"$tmp"
mv "$tmp" "$INI_DST"

echo "==> silk site update + load apps (/relax-api, /relax/*, /relax)"
silk site "${HOST}" update || true
silk app "${HOST}/relax-api*" load
silk app "${HOST}/relax/*" load

cat <<EOF

Done.

  UI:  https://${HOST}/relax/
  API: https://${HOST}/relax-api/health

curl -sS -D - --compressed "https://${HOST}/relax-api/health"
# expect X-Relax-Backend: wsgi-health

If an old catch-all /* Node app still wins, unload it (see silk app help) or ask SAA.
EOF
