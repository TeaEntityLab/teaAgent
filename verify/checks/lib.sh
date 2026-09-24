# shellcheck shell=bash
# Sourced by verify/ scripts and by copy-paste drive commands:
#   source verify/checks/lib.sh
# Scratch workspaces live under ${TMPDIR:-/tmp}; nothing is written inside the repo.

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)}"
T="${TEAAGENT_BIN:-$REPO/.venv/bin/teaagent}"   # CLI under test
P="${PYTHON_BIN:-$REPO/.venv/bin/python}"      # venv python (has pyyaml via dev extras)
FIX="$REPO/verify/fixtures"
export REPO T P FIX

# mk_scratch: print a fresh git workspace initialised with the offline `fake` provider.
# HOME is redirected into the scratch dir so ~/.teaagent/run-keys stays out of the real home.
mk_scratch() {
  local w
  w="$(mktemp -d "${TMPDIR:-/tmp}/teaagent-verify.XXXXXX")"
  mkdir -p "$w/home"
  (
    cd "$w" || exit 1
    export HOME="$w/home"
    git init -q
    git config user.email verify@localhost
    git config user.name verify
    "$T" init --root . --provider fake > /dev/null
    git add -A
    git commit -qm scaffold
  ) || { echo "mk_scratch failed in $w" >&2; return 1; }
  printf '%s\n' "$w"
}

# enter_scratch: create a scratch workspace, cd into it, and isolate HOME for this shell.
enter_scratch() {
  W="$(mk_scratch)" || return 1
  export W HOME="$W/home"
  cd "$W" || return 1
}

# jget EXPR: evaluate a Python expression over JSON on stdin (bound to `d`) and print it.
jget() {
  "$P" -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"
}

# front_matter FILE: print the YAML front matter of a feature file as JSON.
front_matter() {
  "$P" - "$1" <<'PY'
import json, sys, yaml
text = open(sys.argv[1], encoding='utf-8').read()
if not text.startswith('---\n'):
    sys.exit(f'{sys.argv[1]}: missing YAML front matter')
print(json.dumps(yaml.safe_load(text.split('---\n', 2)[1]), default=str))
PY
}
