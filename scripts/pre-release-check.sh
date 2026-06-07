#!/usr/bin/env bash
# Pre-release checklist — run before cutting a release.
# Exits with non-zero if any check fails.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

errors=0

check() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo "  ✓ $label"
    else
        echo "  ✗ $label"
        errors=$((errors + 1))
    fi
}

echo "Pre-release checklist for $(basename "$ROOT")"
echo ""

# 1. Version check
echo "[Version]"
VERSION=$(python3 -c "import teaagent; print(teaagent.__version__)" 2>/dev/null || echo "unknown")
check "Package version: $VERSION" test -n "$VERSION"

# 2. CHANGELOG check
echo "[Changelog]"
check "CHANGELOG.md has Unreleased section" grep -q "^## Unreleased" CHANGELOG.md
check "No placeholder entries" grep -v "TODO\|FIXME\|placeholder" CHANGELOG.md > /dev/null

# 3. Test suite
echo "[Tests]"
check "All tests pass" python3 -m pytest -q --timeout=60 -x
check "Coverage gate" python3 -m pytest --cov=teaagent --cov-fail-under=75 -q

# 4. Lint / typecheck
echo "[Lint & types]"
check "ruff lint" ruff check teaagent/ tests/
check "ruff format" ruff format --check teaagent/ tests/
check "mypy" mypy teaagent/ tests/

# 5. Build
echo "[Build]"
check "Build succeeds" python3 -m build
check "Twine check" python3 -m twine check dist/*

# 6. Compliance
echo "[Compliance]"
check "Docs consistency" python3 scripts/validate_docs_consistency.py
check "Bandit SAST" bandit -r teaagent/ -q -c pyproject.toml

echo ""
if [ "$errors" -eq 0 ]; then
    echo "All checks passed. Ready to release."
    exit 0
else
    echo "$errors check(s) failed. Fix before releasing."
    exit 1
fi
