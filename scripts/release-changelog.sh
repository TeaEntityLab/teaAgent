#!/usr/bin/env bash
# Release changelog helper — move Unreleased entries to a version section.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-}"
CHANGELOG="$ROOT/CHANGELOG.md"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.5.0"
    exit 1
fi

if [ ! -f "$CHANGELOG" ]; then
    echo "Error: CHANGELOG.md not found"
    exit 1
fi

# Check for unreleased section
if ! grep -q "^## Unreleased" "$CHANGELOG"; then
    echo "Error: No '## Unreleased' section found in CHANGELOG.md"
    exit 1
fi

DATE=$(date +%Y-%m-%d)
TMPFILE=$(mktemp)

awk -v ver="$VERSION" -v date="$DATE" '
    /^## Unreleased$/ {
        print "## v" ver " (" date ")"
        in_unreleased = 1
        next
    }
    in_unreleased && /^## / {
        print ""
        print "## Unreleased"
        print ""
        in_unreleased = 0
    }
    { print }
' "$CHANGELOG" > "$TMPFILE"

mv "$TMPFILE" "$CHANGELOG"
echo "Updated CHANGELOG.md: Unreleased → v$VERSION ($DATE)"
