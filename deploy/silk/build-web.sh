#!/usr/bin/env bash
# Build Next standalone with Silk rewrites → deploy/silk/dist/web
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$ROOT/deploy/silk/dist/web"

# Same-origin /api/* (Next proxies to systemd uvicorn)
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/api}"
export SILK_DEPLOY=1
export RELAX_API_UPSTREAM="${RELAX_API_UPSTREAM:-http://127.0.0.1:8000}"

echo "==> Installing frontend deps"
cd "$FRONTEND"
npm ci

echo "==> Building Next standalone (SILK_DEPLOY=1), API_URL=${NEXT_PUBLIC_API_URL}, upstream=${RELAX_API_UPSTREAM}"
npm run build

if [[ ! -f "$FRONTEND/.next/standalone/server.js" ]]; then
  echo "error: standalone server.js missing" >&2
  exit 1
fi

echo "==> Assembling $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$FRONTEND/.next/standalone/." "$OUT/"
mkdir -p "$OUT/.next"
cp -R "$FRONTEND/.next/static" "$OUT/.next/static"
if [[ -d "$FRONTEND/public" ]]; then
  cp -R "$FRONTEND/public" "$OUT/public"
fi
chmod u+x "$OUT/server.js"

echo "==> Web build ready: $OUT"
