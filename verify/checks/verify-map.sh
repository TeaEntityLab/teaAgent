#!/usr/bin/env bash
# Truth layer for verify/refresh.sh (and a standalone map-health check).
# Holds only when:
#   1. constitutional map files are unchanged vs HEAD (everything under verify/ and VERIFY.md
#      except verify/features/*.md),
#   2. no feature's `drive` block differs from HEAD (drives cannot be weakened in-run),
#   3. every feature has well-formed metadata and none is stale
#      (no commit in source_commit..HEAD touches its `covers:` paths),
#   4. drive.sh all passes, and
#   5. acceptance.sh reports no FAIL/XPASS.
# exit: 0 holds, 1 does not hold, 4 harness broken
set -uo pipefail
# shellcheck source=verify/checks/lib.sh
source "$(dirname "$0")/lib.sh"
cd "$REPO" || exit 4
[ -x "$T" ] || { echo "HARNESS: $T missing" >&2; exit 4; }

fail=0
note() { echo "MAP: $*"; fail=1; }

# 1. constitutional paths
changed="$(git status --porcelain --untracked-files=all -- VERIFY.md verify | awk '{print $NF}' | grep -Ev '^verify/features/[^/]+\.md$' || true)"
[ -z "$changed" ] || note "constitutional files changed: $(echo "$changed" | tr '\n' ' ')"

# 2 + 3. per-feature drive lock, metadata, staleness
for f in verify/features/*.md; do
  [ "$(basename "$f")" = README.md ] && continue
  fm="$(front_matter "$f")" || { note "$f: unreadable front matter"; continue; }
  if git cat-file -e "HEAD:$f" 2> /dev/null; then
    head_drive="$(git show "HEAD:$f" > "${TMPDIR:-/tmp}/vm-head.$$" && front_matter "${TMPDIR:-/tmp}/vm-head.$$" | jget 'json.dumps(d["drive"], sort_keys=True)' 2> /dev/null)"
    rm -f "${TMPDIR:-/tmp}/vm-head.$$"
    [ "$(printf '%s' "$fm" | jget 'json.dumps(d["drive"], sort_keys=True)')" = "$head_drive" ] || note "$f: drive block differs from HEAD"
  fi
  printf '%s' "$fm" | jget 'all(k in d for k in ("feature","source_commit","last_verified_at","verification_status","covers","drive")) and d["verification_status"] in ("passed","failed","unverified") and (d["verification_status"] != "failed" or bool(d.get("known_findings")))' | grep -qx True \
    || note "$f: metadata missing/invalid (failed status requires known_findings)"
  sc="$(printf '%s' "$fm" | jget 'd["source_commit"]')"
  covers=()
  while IFS= read -r c; do covers+=("$c"); done < <(printf '%s' "$fm" | jget '"\n".join(d["covers"])')
  git cat-file -e "$sc^{commit}" 2> /dev/null || { note "$f: source_commit $sc not found"; continue; }
  n="$(git rev-list --count "$sc..HEAD" -- "${covers[@]}")"
  [ "$n" = 0 ] || note "$f: STALE ($n commits touch covered paths since $sc)"
done

# 4 + 5. behaviour
verify/checks/drive.sh all || note "drive.sh all failed"
verify/checks/acceptance.sh || note "acceptance.sh reported FAIL/XPASS"

[ "$fail" = 0 ] && echo "MAP OK"
exit "$fail"
