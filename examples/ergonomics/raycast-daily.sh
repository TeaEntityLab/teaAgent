#!/usr/bin/env bash
# Raycast / Shortcuts: open today's journal path after a daily brief.
set -euo pipefail
ROOT="${1:-.}"
PROVIDER="${TEAAGENT_PROVIDER:-gpt}"
teaagent agent daily "$PROVIDER" --root "$ROOT" --write-journal
open "$(dirname "$(teaagent journal "$PROVIDER" --root "$ROOT" 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["path"])' 2>/dev/null || echo .)")" 2>/dev/null || true
