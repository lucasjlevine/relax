#!/usr/bin/env bash
# Run ON Silk from the repo root (or this script's location), when the clone is at
# ~/www-root/relax. Builds the frontend, installs API deps, installs .silk.ini.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE_ROOT="$(cd "$ROOT/.." && pwd)"
NETID="${NETID:-jlhorton}"
VENV="${VENV:-$HOME/venvs/relax}"

echo "==> Repo:       $ROOT"
echo "==> Site root:  $SITE_ROOT"
echo "==> Expected:   \$HOME/www-root/relax → site .silk.ini at \$HOME/www-root/.silk.ini"

if [[ "$(basename "$ROOT")" != "relax" ]] || [[ "$(basename "$SITE_ROOT")" != "www-root" ]]; then
  echo "warning: expected ~/www-root/relax; got ROOT=$ROOT SITE_ROOT=$SITE_ROOT" >&2
  echo "         continuing — override SITE_ROOT if needed" >&2
fi

mkdir -p "$SITE_ROOT/public" "$HOME/venvs"

echo "==> Building Next.js standalone → deploy/silk/dist/web"
"$ROOT/deploy/silk/build-web.sh"

if [[ ! -f "$ROOT/deploy/silk/dist/web/server.js" ]]; then
  echo "error: missing $ROOT/deploy/silk/dist/web/server.js after build" >&2
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  echo "==> Creating venv at $VENV"
  python3 -m venv "$VENV"
fi

echo "==> pip install backend into venv"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install "$ROOT/backend"

chmod u+x "$ROOT/backend/wsgi.py" "$ROOT/deploy/silk/dist/web/server.js"
mkdir -p "$ROOT/backend/data/uploads" "$ROOT/backend/data/user_datasets"

INI_SRC="$ROOT/deploy/silk/.silk.ini"
INI_DST="$SITE_ROOT/.silk.ini"
echo "==> Installing $INI_DST"
cp "$INI_SRC" "$INI_DST"

# Ensure venv-path in .silk.ini matches this machine
ABS_VENV="$(readlink -f "$VENV" 2>/dev/null || realpath "$VENV")"
if grep -q '^venv-path' "$INI_DST"; then
  # portable sed: rewrite venv-path line
  tmp="$(mktemp)"
  sed "s|^venv-path = .*|venv-path = ${ABS_VENV}|" "$INI_DST" >"$tmp"
  mv "$tmp" "$INI_DST"
fi

echo "==> silk update + load apps"
silk update || true
silk app "${NETID}.w3.uvm.edu/api" load
silk app "${NETID}.w3.uvm.edu" load

cat <<EOF

Done.

Smoke checks:
  https://${NETID}.w3.uvm.edu/api/health
  https://${NETID}.w3.uvm.edu/calc

If load fails, check Unit logs (see Silk Node/Python manual) and confirm:
  - $INI_DST exists at site root
  - $ROOT/deploy/silk/dist/web/server.js exists (run build-web.sh)
  - $ROOT/backend/wsgi.py is executable
  - venv-path is $ABS_VENV
EOF
