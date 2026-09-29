#!/usr/bin/env bash
# Stage FastAPI sources into deploy/silk/dist/api for Silk.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
OUT="$ROOT/deploy/silk/dist/api"

echo "==> Assembling $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

cp -R "$BACKEND/app" "$OUT/app"
cp -R "$BACKEND/data" "$OUT/data"
cp "$BACKEND/wsgi.py" "$OUT/wsgi.py"
cp "$BACKEND/pyproject.toml" "$OUT/pyproject.toml"
cp "$BACKEND/README.md" "$OUT/README.md"
chmod u+x "$OUT/wsgi.py"

# Writable runtime dirs (created empty if missing)
mkdir -p "$OUT/data/uploads" "$OUT/data/user_datasets"
# Do not ship local upload/user JSON scratch into dist if present
rm -rf "$OUT/data/uploads/"* 2>/dev/null || true
find "$OUT/data/user_datasets" -type f -name '*.json' -delete 2>/dev/null || true

echo "==> API tree ready: $OUT"
echo "    On Silk, create a venv and: pip install '$OUT'  (or rsync then pip install .)"
