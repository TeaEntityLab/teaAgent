#!/usr/bin/env bash
# generated-by: flow-control-generator / parallel fan-out + deterministic fan-in / 2026-09-24 / stub dry-run verified
# Fresh-agent sweep: one read-only verifier per feature file, then a deterministic verdict tally.
# Budget: MAX_JOBS concurrent verifiers (default 2; each runs pytest + CLI drives), one agent call
# per feature, AGENT_TIMEOUT per call where timeout/gtimeout exists (see run-verifier.sh).
# Permission boundary: run-verifier.sh read-only (no Edit/Write; Bash only verify/checks/*.sh, git log/diff/show).
# exit: 0 every feature PASS | 2 at least one non-PASS verdict (human classifies) | 3 branch failed or verdict malformed | 4 harness
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(cd "$HERE/.." && pwd -P)"
RUN="${RUN:-$HERE/run-verifier.sh}"
MAX_JOBS="${MAX_JOBS:-2}"
MODEL="${MODEL:-}"
STATE="${STATE:-$(mktemp -d "${TMPDIR:-/tmp}/teaagent-sweep.XXXXXX")}"
mkdir -p "$STATE"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$STATE/flow.log"; }

features=()
for f in "$REPO"/verify/features/*.md; do
  [ "$(basename "$f")" = README.md ] || features+=("$(basename "$f" .md)")
done
[ "${#features[@]}" -gt 0 ] || { echo "no feature files" >&2; exit 4; }
rm -f "$STATE"/fan-*.md   # stale outputs from a prior run must not satisfy the gate

branch() {  # $1 = feature name; state/fan-<name>.md is the only payload
  local name="$1"
  { cat "$REPO/verify/governance/verifier-agent.md"
    printf '\n## Assignment\n\nFeature file: verify/features/%s.md\nRepository root: %s\n' "$name" "$REPO"
  } > "$STATE/prompt-$name.md"
  log "start $name"
  if "$RUN" read-only "$REPO" "$STATE/prompt-$name.md" $MODEL > "$STATE/fan-$name.md" 2> "$STATE/fan-$name.err"; then
    log "done  $name"
  else
    log "fail  $name"; return 1
  fi
}

FAILED=0
wave_wait() { local pid; for pid in "$@"; do wait "$pid" || FAILED=$((FAILED + 1)); done; }
pids=(); i=0
for name in "${features[@]}"; do
  branch "$name" &
  pids+=($!); i=$((i + 1))
  if [ $((i % MAX_JOBS)) -eq 0 ]; then wave_wait "${pids[@]}"; pids=(); fi
done
if [ "${#pids[@]}" -gt 0 ]; then wave_wait "${pids[@]}"; fi

# Fan-in gate (deterministic): each branch's last non-empty line is exactly one verdict.
malformed=0; nonpass=0
{
  echo "# Sweep summary ($(date -u +%Y-%m-%dT%H:%M:%SZ), HEAD $(git -C "$REPO" rev-parse --short HEAD))"
  echo
  for name in "${features[@]}"; do
    out="$STATE/fan-$name.md"
    verdict="$( [ -s "$out" ] && sed '/^[[:space:]]*$/d' "$out" | tail -n1 || true)"
    case "$verdict" in
      "VERDICT: PASS") echo "- $name: PASS" ;;
      "VERDICT: PRODUCT_REGRESSION" | "VERDICT: DOC_DRIFT" | "VERDICT: SPEC_ORACLE_ERROR" | "VERDICT: HARNESS_FAILURE")
        echo "- $name: ${verdict#VERDICT: } (see $out)"; nonpass=$((nonpass + 1)) ;;
      *) echo "- $name: MALFORMED (no verdict line; see $out)"; malformed=$((malformed + 1)) ;;
    esac
  done
} > "$STATE/summary.md"
log "fan-in: failed=$FAILED malformed=$malformed nonpass=$nonpass"
cat "$STATE/summary.md"
echo "state: $STATE"
[ "$FAILED" -eq 0 ] && [ "$malformed" -eq 0 ] || exit 3
[ "$nonpass" -eq 0 ] || exit 2
