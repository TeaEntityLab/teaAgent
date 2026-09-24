#!/usr/bin/env bash
# Run the `drive` items declared in verify/features/<name>.md front matter.
# Each item runs in its own fresh scratch workspace (see lib.sh enter_scratch).
# usage: verify/checks/drive.sh <feature>... | all
# exit: 0 all pass, 1 any item failed, 4 harness broken, 64 usage
set -euo pipefail
# shellcheck source=verify/checks/lib.sh
source "$(dirname "$0")/lib.sh"

[ -x "$T" ] || { echo "HARNESS: $T missing; run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2; exit 4; }
[ "$#" -gt 0 ] || { echo "usage: $0 <feature>... | all" >&2; exit 64; }

names=()
if [ "$1" = all ]; then
  for f in "$REPO"/verify/features/*.md; do
    b="$(basename "$f" .md)"
    [ "$b" = README ] || names+=("$b")
  done
else
  names=("$@")
fi

LOGS="${VERIFY_LOG_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/teaagent-verify-logs.XXXXXX")}"
mkdir -p "$LOGS"
fail=0
for name in "${names[@]}"; do
  file="$REPO/verify/features/$name.md"
  [ -f "$file" ] || { echo "no feature file: $file" >&2; exit 64; }
  fm="$(front_matter "$file")"
  count="$(printf '%s' "$fm" | jget 'len(d["drive"])')"
  i=0
  while [ "$i" -lt "$count" ]; do
    id="$(printf '%s' "$fm" | jget "d['drive'][$i]['id']")"
    cmd="$(printf '%s' "$fm" | jget "d['drive'][$i]['run']")"
    log="$LOGS/$name--$id.log"
    start=$(date +%s)
    if bash -euo pipefail -c "source \"$REPO/verify/checks/lib.sh\"; enter_scratch; echo \"scratch: \$W\"; set -x; $cmd" > "$log" 2>&1; then
      echo "PASS $name/$id ($(( $(date +%s) - start ))s)"
    else
      echo "FAIL $name/$id ($(( $(date +%s) - start ))s) log=$log"
      fail=1
    fi
    i=$((i + 1))
  done
done
echo "logs: $LOGS"
exit "$fail"
