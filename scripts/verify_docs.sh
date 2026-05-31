#!/usr/bin/env bash
# Local docs gate (TASK-034): run before release or when editing docs/.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/validate_docs_consistency.py
echo "Docs verification passed."
