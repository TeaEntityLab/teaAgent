#!/usr/bin/env bash
# Export pinned transitive dependencies for release builds.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${1:-requirements-frozen.txt}"
uv export --format requirements-txt --no-emit-project --frozen -o "$OUT"
echo "Wrote $OUT"
