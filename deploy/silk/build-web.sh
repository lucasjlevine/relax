#!/usr/bin/env bash
# Build Next.js standalone with basePath=/relax into deploy/silk/dist/web.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$ROOT/deploy/silk/dist/web"

# Relative API root on the Silk host (non-overlapping with /relax)
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-/relax-api}"
export SILK_DEPLOY=1

echo "==> Installing frontend deps"
cd "$FRONTEND"
npm ci

echo "==> Building Next.js standalone (SILK_DEPLOY=1 basePath=/relax), API=${NEXT_PUBLIC_API_URL}"
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
echo "    UI:  https://HOST/relax/   API: https://HOST/relax-api/"
