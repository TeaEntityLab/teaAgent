#!/usr/bin/env bash
# Generate CHANGELOG section from conventional commits (DOC-006 / GOV-004).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v git-cliff >/dev/null 2>&1; then
  git-cliff --config cliff.toml --unreleased --prepend CHANGELOG.md
  echo "Updated CHANGELOG.md from git-cliff"
  exit 0
fi

if uv run python -c "import scriv" 2>/dev/null; then
  uv run scriv collect
  echo "Collected scriv fragments into CHANGELOG.md"
  exit 0
fi

echo "Install git-cliff or scriv to generate changelog entries" >&2
exit 1
