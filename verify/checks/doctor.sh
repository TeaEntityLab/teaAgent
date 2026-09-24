#!/usr/bin/env bash
# Fast smoke (~10s): harness present, CLI boots, offline fake run completes and its
# audit chain verifies. `--tests` adds the repo smoke tier (~25s).
# exit: 0 healthy, 1 product check failed, 4 harness broken
set -euo pipefail
# shellcheck source=verify/checks/lib.sh
source "$(dirname "$0")/lib.sh"

[ -x "$T" ] && [ -x "$P" ] || { echo "HARNESS: missing $T or $P; run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2; exit 4; }
"$P" -c 'import yaml' 2>/dev/null || { echo "HARNESS: pyyaml missing from $P (dev extras install it via pre-commit)" >&2; exit 4; }
git --version > /dev/null || { echo "HARNESS: git missing" >&2; exit 4; }

step() { printf '%-34s' "$1"; }
ok() { echo "ok${1:+ ($1)}"; }
bad() { echo "FAIL: $1"; exit 1; }

step "cli boots"; "$T" --version > /dev/null || bad "teaagent --version"; ok
step "scratch workspace (fake provider)"; enter_scratch || exit 4; ok "$W"
step "selftest"; [ "$("$T" selftest --root . | jget 'd["ok"]')" = True ] || bad "selftest ok!=true"; ok
step "tool contract lint"; [ "$("$T" tool lint --root . | jget 'd["error_count"]')" = 0 ] || bad "tool lint errors"; ok
step "offline run completes"
out="$("$T" run fake "say hi" --root . --json --no-summary 2> /dev/null)" || bad "run exit $?"
[ "$(printf '%s' "$out" | jget 'd["audit_summary"]["status"]')" = completed ] || bad "status != completed"
run_id="$(printf '%s' "$out" | jget 'd["run_id"]')"; ok "$run_id"
step "audit chain verifies"; [ "$("$T" audit verify "$run_id" --root . --ci | jget 'd["status"]')" = valid ] || bad "chain invalid"; ok

if [ "${1:-}" = --tests ]; then
  step "smoke test tier"; (cd "$REPO" && "$P" scripts/run_test_tier.py --tier smoke > "$W/smoke.log" 2>&1) || bad "see $W/smoke.log"; ok "$(tail -n1 "$W/smoke.log")"
fi
echo "DOCTOR OK"
