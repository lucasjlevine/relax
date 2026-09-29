#!/usr/bin/env bash
# Build Next.js static export into deploy/silk/dist/web for Silk document-root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$ROOT/deploy/silk/dist/web"

# Same-origin: browser calls /api/* on the Silk hostname (Unit → FastAPI).
# Do NOT set NODE_ENV=production before npm ci — that skips devDependencies.
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-}"
export SILK_STATIC=1

echo "==> Installing frontend deps"
cd "$FRONTEND"
npm ci

echo "==> Building Next.js static export (SILK_STATIC=1), NEXT_PUBLIC_API_URL='${NEXT_PUBLIC_API_URL}'"
npm run build

if [[ ! -f "$FRONTEND/out/index.html" ]]; then
  echo "error: frontend/out/index.html missing after export build" >&2
  exit 1
fi

echo "==> Assembling $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$FRONTEND/out/." "$OUT/"

echo "==> Static web build ready: $OUT"
echo "    Point Silk [general] document-root at relax/deploy/silk/dist/web"
