#!/usr/bin/env bash
# generated-by: flow-loop-harness / verify-gated fix loop / 2026-09-24 / stub dry-run verified (exits 0,2,3,4)
# Re-verify stale feature files until verify/checks/verify-map.sh holds.
# The loop body may edit only verify/features/*.md; the verifier and a scope guard decide.
# exit: 0 map verified | 2 MAX_ITER exhausted | 3 no progress, scope violation, or agent STOP | 4 verifier broken
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(cd "$HERE/.." && pwd -P)"
RUN="${RUN:-$HERE/run-verifier.sh}"                  # permission boundary: workspace-write = Edit/Write verify/features/** only
VERIFY="${VERIFY:-$HERE/checks/verify-map.sh}"      # truth layer: exit 0 = map verified
MAX_ITER="${MAX_ITER:-5}"                            # one stale feature per iteration; 5 features mapped
STATE="${STATE:-${TMPDIR:-/tmp}/teaagent-refresh}"   # outside the repo: never counted as progress or scope
MODEL="${MODEL:-}"
mkdir -p "$STATE"
LEDGER="$STATE/ledger.md"; touch "$LEDGER"
cd "$REPO"

[ -x "$VERIFY" ] || { echo "verifier missing/not executable: $VERIFY" >&2; exit 4; }

check() { local ec=0; "$VERIFY" > "$STATE/verify-out.txt" 2>&1 || ec=$?; return "$ec"; }
snapshot() { git diff HEAD --stat -- verify/features | tail -n1; git status --porcelain --untracked-files=all | wc -l | tr -d ' '; }
out_of_scope() {  # anything changed outside verify/features/*.md
  git status --porcelain --untracked-files=all | awk '{print $NF}' | grep -Ev '^verify/features/[^/]+\.md$' || true
}

[ ! -s "$LEDGER" ] || echo "- RESUMED $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LEDGER"
[ -z "$(out_of_scope)" ] || { echo "- preflight: worktree dirty outside verify/features; refusing to start" >> "$LEDGER"; exit 3; }
if check; then echo "- already verified" >> "$LEDGER"; echo "already verified"; exit 0; fi

prev="$(snapshot)"
for i in $(seq 1 "$MAX_ITER"); do
  {
    cat "$HERE/prompts/refresh.md"
    printf '\n## Run facts\n\nHEAD: %s\nUTC date: %s\n' "$(git rev-parse --short HEAD)" "$(date -u +%Y-%m-%d)"
    printf '\n## Ledger tail\n\n'; tail -n 20 "$LEDGER"
    printf '\n## Verifier output (MAP lines)\n\n'; grep -E '^(MAP|FAIL|XPASS)' "$STATE/verify-out.txt" || true
  } > "$STATE/iter-$i-prompt.md"

  "$RUN" workspace-write "$REPO" "$STATE/iter-$i-prompt.md" $MODEL > "$STATE/iter-$i-out.md" 2> "$STATE/iter-$i-err.txt" || true

  scope="$(out_of_scope)"
  if [ -n "$scope" ]; then
    echo "- iter $i: SCOPE VIOLATION: $(echo "$scope" | tr '\n' ' ')" >> "$LEDGER"; exit 3
  fi
  if stop="$(grep -m1 -E '^STOP: ' "$STATE/iter-$i-out.md")"; then
    echo "- iter $i: agent $stop" >> "$LEDGER"; exit 3
  fi
  if check; then echo "- iter $i: VERIFIED" >> "$LEDGER"; exit 0; fi
  cur="$(snapshot)"
  echo "- iter $i: not verified; sig: $(echo "$cur" | tr '\n' ' ')" >> "$LEDGER"
  if [ "$cur" = "$prev" ]; then echo "- iter $i: NO PROGRESS, aborting" >> "$LEDGER"; exit 3; fi
  prev="$cur"
done
echo "- cap $MAX_ITER exhausted" >> "$LEDGER"; exit 2
