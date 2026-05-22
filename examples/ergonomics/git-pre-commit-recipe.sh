#!/usr/bin/env bash
# Example git hook: run the built-in review-staged recipe before commit.
set -euo pipefail
teaagent recipes run review-staged --print-only >/dev/null
teaagent ci review --provider "${TEAAGENT_PROVIDER:-gpt}" --root "$(git rev-parse --show-toplevel)"
