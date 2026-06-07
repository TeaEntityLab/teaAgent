#!/usr/bin/env bash
# Validate example scripts (syntax/import smoke).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
for f in examples/*.py; do
  echo "Checking $f"
  python3 -m py_compile "$f"
done
echo "All examples OK"
