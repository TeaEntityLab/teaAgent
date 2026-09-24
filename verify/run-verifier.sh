#!/usr/bin/env bash
# Run interface (agent-governance-scaffold §15.2) for map verifiers:
#   verify/run-verifier.sh <read-only|workspace-write> <workdir> <prompt-file> [model]
# The prompt is passed on stdin; stdout is the agent's report.
#   read-only       Read/Grep/Glob + Bash limited to verify/checks/{doctor,drive,acceptance}.sh and git log/diff/show.
#   workspace-write read-only set + Edit/Write limited to verify/features/**.
#                   refresh.sh re-checks the resulting diff; this allowlist alone is not the gate.
# AGENT_CMD overrides the host (stub dry runs, other CLIs). An override receives the same
# stdin contract but NOT the allowlist below; callers keep their own deterministic gates.
# AGENT_TIMEOUT (seconds, default 1800) applies when timeout/gtimeout exists on PATH.
set -euo pipefail

mode="${1:-}"; workdir="${2:-}"; prompt="${3:-}"; model="${4:-}"
case "$mode" in
  read-only | workspace-write) ;;
  *) echo "usage: $0 <read-only|workspace-write> <workdir> <prompt-file> [model]" >&2; exit 64 ;;
esac
[ -d "$workdir" ] || { echo "workdir not found: $workdir" >&2; exit 64; }
[ -f "$prompt" ] || { echo "prompt file not found: $prompt" >&2; exit 64; }
prompt="$(cd "$(dirname "$prompt")" && pwd -P)/$(basename "$prompt")"

wrap=()
to="$(command -v timeout || command -v gtimeout || true)"
[ -z "$to" ] || wrap=("$to" "${AGENT_TIMEOUT:-1800}")

cd "$workdir"
if [ -n "${AGENT_CMD:-}" ]; then
  # shellcheck disable=SC2086  # AGENT_CMD is a command line by contract
  exec ${wrap[@]+"${wrap[@]}"} $AGENT_CMD < "$prompt"
fi

allowed=(Read Grep Glob "Bash(verify/checks/doctor.sh:*)" "Bash(verify/checks/drive.sh:*)" "Bash(verify/checks/acceptance.sh:*)"
  "Bash(git log:*)" "Bash(git diff:*)" "Bash(git show:*)")
if [ "$mode" = workspace-write ]; then
  allowed+=("Edit(verify/features/**)" "Write(verify/features/**)")
fi
args=(-p --allowedTools "${allowed[@]}" --disallowedTools NotebookEdit WebFetch WebSearch)
[ -z "$model" ] || args+=(--model "$model")
exec ${wrap[@]+"${wrap[@]}"} claude "${args[@]}" < "$prompt"
