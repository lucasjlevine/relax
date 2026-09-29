#!/usr/bin/env bash
# Run ON Silk from ~/www-root/relax.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"
HOST="${NETID}.w3.uvm.edu"
PUBLIC_RELAX="${SITE_ROOT}/public/relax"

echo "==> Repo:      $ROOT"
echo "==> Site root: $SITE_ROOT"
echo "==> Static UI: $PUBLIC_RELAX"

mkdir -p "$SITE_ROOT/public" "$HOME/venvs"

echo "==> Build static UI"
"$ROOT/deploy/silk/build-web.sh"

echo "==> Publish static UI → $PUBLIC_RELAX"
rm -rf "$PUBLIC_RELAX"
mkdir -p "$PUBLIC_RELAX"
cp -R "$ROOT/deploy/silk/dist/web/." "$PUBLIC_RELAX/"

if [[ ! -d "$VENV" ]]; then
  echo "==> Creating venv $VENV"
  python3 -m venv "$VENV"
fi

echo "==> pip install backend"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install "$ROOT/backend"

# Quick duckdb import check (native wheel often breaks → proxy errors)
if ! "$VENV/bin/python" -c "import duckdb; print('duckdb', duckdb.__version__)"; then
  echo "error: duckdb failed to import in $VENV — API will crash under Unit" >&2
  exit 1
fi

chmod u+x "$ROOT/backend/wsgi.py"
mkdir -p "$ROOT/backend/data/uploads" "$ROOT/backend/data/user_datasets"

INI_DST="$SITE_ROOT/.silk.ini"
cp "$ROOT/deploy/silk/.silk.ini" "$INI_DST"
ABS_VENV="$(readlink -f "$VENV" 2>/dev/null || realpath "$VENV")"
tmp="$(mktemp)"
sed "s|^venv-path = .*|venv-path = ${ABS_VENV}|" "$INI_DST" >"$tmp"
mv "$tmp" "$INI_DST"

echo "==> Kill stale Node Unit workers (Next-on-Unit is unsupported)"
FORCE=1 "$ROOT/deploy/silk/kill-stale-apps.sh" || true

echo "==> silk site update + load API only"
silk site "${HOST}" update || true
silk app "${HOST}/relax-api" load

cat <<EOF

Done. There should be NO nodejs Unit app — only relax_api.

  UI (static):  https://${HOST}/relax/
  API:          https://${HOST}/relax-api/health

curl -sS -D - --compressed "https://${HOST}/relax-api/health"

If API still proxy-errors, check Unit logs and PATH_INFO:
  ls /var/opt/nginx-unit/*/unit.log /usr/lib/unit-user-*/unit.log 2>/dev/null
  tail -80 /var/opt/nginx-unit/*/unit.log 2>/dev/null

Unload old Node apps if they still appear in 'ps':
  silk app help
  # or kill node PIDs again after confirming .silk.ini has no type=nodejs
EOF
