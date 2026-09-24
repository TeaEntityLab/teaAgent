#!/usr/bin/env bash
# Evaluate the locked oracle verify/acceptance.yaml. Each check runs in a fresh scratch workspace.
# Result per check: PASS | FAIL (expected_pass broke) | XFAIL (known_failing still fails) |
#                   XPASS (known_failing now holds -> update finding + map).
# exit: 0 no FAIL/XPASS, 1 FAIL or XPASS present, 4 harness broken
set -euo pipefail
# shellcheck source=verify/checks/lib.sh
source "$(dirname "$0")/lib.sh"

[ -x "$T" ] || { echo "HARNESS: $T missing" >&2; exit 4; }
spec="$REPO/verify/acceptance.yaml"
checks="$("$P" -c 'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))["checks"]))' "$spec")" \
  || { echo "HARNESS: cannot parse $spec" >&2; exit 4; }
count="$(printf '%s' "$checks" | jget 'len(d)')"

LOGS="${VERIFY_LOG_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/teaagent-verify-logs.XXXXXX")}"
mkdir -p "$LOGS"
bad=0
i=0
while [ "$i" -lt "$count" ]; do
  id="$(printf '%s' "$checks" | jget "d[$i]['id']")"
  status="$(printf '%s' "$checks" | jget "d[$i]['status']")"
  finding="$(printf '%s' "$checks" | jget "d[$i].get('finding', '')")"
  cmd="$(printf '%s' "$checks" | jget "d[$i]['run']")"
  log="$LOGS/acceptance--$id.log"
  if bash -euo pipefail -c "source \"$REPO/verify/checks/lib.sh\"; enter_scratch; echo \"scratch: \$W\"; set -x; $cmd" > "$log" 2>&1; then held=1; else held=0; fi
  case "$status:$held" in
    expected_pass:1) echo "PASS  $id" ;;
    expected_pass:0) echo "FAIL  $id log=$log"; bad=1 ;;
    known_failing:0) echo "XFAIL $id ($finding)" ;;
    known_failing:1) echo "XPASS $id ($finding now holds: update finding status and map)"; bad=1 ;;
    *) echo "HARNESS: $id has unknown status '$status'" >&2; exit 4 ;;
  esac
  i=$((i + 1))
done
echo "logs: $LOGS"
exit "$bad"
