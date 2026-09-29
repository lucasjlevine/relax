#!/usr/bin/env bash
# Build Next.js standalone output into deploy/silk/dist/web for Silk.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$ROOT/deploy/silk/dist/web"

# Same-origin: browser calls /api/* on the Silk hostname (Unit routes to FastAPI).
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-}"
export NODE_ENV=production

echo "==> Installing frontend deps"
cd "$FRONTEND"
npm ci

echo "==> Building Next.js (standalone), NEXT_PUBLIC_API_URL='${NEXT_PUBLIC_API_URL}'"
npm run build

if [[ ! -f "$FRONTEND/.next/standalone/server.js" ]]; then
  echo "error: standalone server.js missing; ensure next.config has output: 'standalone'" >&2
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
