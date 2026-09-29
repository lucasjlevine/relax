#!/usr/bin/env bash
# Run ON Silk from ~/www-root/relax. Builds static UI, installs API, wires .silk.ini.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"

echo "==> Repo:       $ROOT"
echo "==> Site root:  $SITE_ROOT"

if [[ "$(basename "$ROOT")" != "relax" ]] || [[ "$(basename "$SITE_ROOT")" != "www-root" ]]; then
  echo "warning: expected ~/www-root/relax; got ROOT=$ROOT SITE_ROOT=$SITE_ROOT" >&2
fi

mkdir -p "$HOME/venvs"

echo "==> Building static Next export → deploy/silk/dist/web"
"$ROOT/deploy/silk/build-web.sh"

if [[ ! -f "$ROOT/deploy/silk/dist/web/index.html" ]]; then
  echo "error: missing $ROOT/deploy/silk/dist/web/index.html after build" >&2
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  echo "==> Creating venv at $VENV"
  python3 -m venv "$VENV"
fi

echo "==> pip install backend into venv"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install "$ROOT/backend"

chmod u+x "$ROOT/backend/wsgi.py"
mkdir -p "$ROOT/backend/data/uploads" "$ROOT/backend/data/user_datasets"

INI_SRC="$ROOT/deploy/silk/.silk.ini"
INI_DST="$SITE_ROOT/.silk.ini"
echo "==> Installing $INI_DST"
cp "$INI_SRC" "$INI_DST"

ABS_VENV="$(readlink -f "$VENV" 2>/dev/null || realpath "$VENV")"
tmp="$(mktemp)"
sed "s|^venv-path = .*|venv-path = ${ABS_VENV}|" "$INI_DST" >"$tmp"
mv "$tmp" "$INI_DST"

echo "==> silk site update + load API only (UI is static document-root)"
silk site "${NETID}.w3.uvm.edu" update || true
# Drop any old catch-all Node app if Silk still has it registered from earlier deploys.
# Loading /api registers the Python app; static files need no app load.
silk app "${NETID}.w3.uvm.edu/api" load

cat <<EOF

Done.

Smoke checks:
  curl -sS -D - --compressed "https://${NETID}.w3.uvm.edu/api/health"
  # expect: X-Relax-Backend: wsgi-health  and  {"status":"ok","via":"wsgi"}
  open https://${NETID}.w3.uvm.edu/calc

If /api still 404s from Next, the old Node Unit app may still be loaded.
Check unit logs and ask Silk/SAA to clear stale apps, or try:
  silk app ${NETID}.w3.uvm.edu load
only after removing the [app: web] section (already removed from .silk.ini).

Confirm:
  - $INI_DST has document-root = relax/deploy/silk/dist/web
  - only [app: api] with uri = /api*
  - $ROOT/deploy/silk/dist/web/index.html exists
  - venv-path is $ABS_VENV
EOF
