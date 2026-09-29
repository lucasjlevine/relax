#!/usr/bin/env bash
# Static Next export with basePath=/relax → deploy/silk/dist/web
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$ROOT/deploy/silk/dist/web"

export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/relax-api}"
export SILK_DEPLOY=1

echo "==> Installing frontend deps"
cd "$FRONTEND"
npm ci

echo "==> Static export (SILK_DEPLOY=1), API=${NEXT_PUBLIC_API_URL}"
npm run build

if [[ ! -f "$FRONTEND/out/index.html" ]]; then
  echo "error: frontend/out/index.html missing" >&2
  exit 1
fi

echo "==> Assembling $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$FRONTEND/out/." "$OUT/"

echo "==> Ready: $OUT (install copies this to ~/www-root/public/relax/)"
