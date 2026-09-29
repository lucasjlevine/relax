#!/usr/bin/env bash
# Rsync built web + api trees to a Silk account site root over SSH.
#
# Usage:
#   ./deploy/silk/sync-to-silk.sh NETID
#   SITE_ROOT=~/www-root ./deploy/silk/sync-to-silk.sh NETID
#   SILK_HOST=w3.uvm.edu ./deploy/silk/sync-to-silk.sh NETID
#
# Prerequisites: run build-web.sh and prepare-api.sh first (or pass --build).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/deploy/silk/dist"
SILK_HOST="${SILK_HOST:-w3.uvm.edu}"
SITE_ROOT="${SITE_ROOT:-~/www-root}"
DO_BUILD=0

usage() {
  echo "Usage: $0 [--build] <NETID>" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) DO_BUILD=1; shift ;;
    -h|--help) usage ;;
    *) break ;;
  esac
done

NETID="${1:-}"
[[ -n "$NETID" ]] || usage

if [[ "$DO_BUILD" -eq 1 ]]; then
  "$ROOT/deploy/silk/build-web.sh"
  "$ROOT/deploy/silk/prepare-api.sh"
fi

[[ -d "$DIST/web" && -d "$DIST/api" ]] || {
  echo "error: missing dist/web or dist/api — run with --build or build scripts first" >&2
  exit 1
}

REMOTE="${NETID}@${SILK_HOST}"
# Expand ~ on the remote via SSH
REMOTE_ROOT="$(ssh "$REMOTE" "echo $SITE_ROOT")"

echo "==> Syncing to ${REMOTE}:${REMOTE_ROOT}"
ssh "$REMOTE" "mkdir -p '${REMOTE_ROOT}/web' '${REMOTE_ROOT}/api' '${REMOTE_ROOT}/public'"

rsync -avz --delete \
  "$DIST/web/" "${REMOTE}:${REMOTE_ROOT}/web/"

rsync -avz --delete \
  --exclude 'data/uploads/' \
  --exclude 'data/user_datasets/*.json' \
  "$DIST/api/" "${REMOTE}:${REMOTE_ROOT}/api/"

if [[ -d "$ROOT/deploy/silk/public" ]]; then
  rsync -avz "$ROOT/deploy/silk/public/" "${REMOTE}:${REMOTE_ROOT}/public/"
fi

if [[ -f "$ROOT/deploy/silk/.silk.ini" ]]; then
  echo "==> Note: edit and install .silk.ini on Silk if not already present:"
  echo "    scp deploy/silk/.silk.ini ${REMOTE}:${REMOTE_ROOT}/.silk.ini"
fi

cat <<EOF

Sync done.

On Silk (${REMOTE}):
  1. Create venv (once):  python3 -m venv ~/venvs/relax && ~/venvs/relax/bin/pip install '${REMOTE_ROOT}/api'
  2. Edit ${REMOTE_ROOT}/.silk.ini  (NETID, venv-path, CORS_ORIGINS)
  3. silk site ${NETID}.w3.uvm.edu update
  4. silk app ${NETID}.w3.uvm.edu/api load
  5. silk app ${NETID}.w3.uvm.edu load
  6. Open https://${NETID}.w3.uvm.edu/calc

See docs/silk-deploy.md for details.
EOF
