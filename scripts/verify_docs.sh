#!/usr/bin/env bash
# Local docs gate (TASK-034): run before release or when editing docs/.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/generate_docs_inventory.py --check
python3 scripts/report_docs_aging.py --check
python3 scripts/generate_command_snippet_inventory.py --check
python3 scripts/build_release_docs_evidence_bundle.py --check
python3 scripts/generate_okf_docs_bundle.py --check
python3 scripts/generate_okf_docs_bundle.py --manifest docs/okf-catalog-reference.yaml --output knowledge/teaagent-reference --check
python3 scripts/generate_okf_docs_bundle.py --manifest docs/okf-catalog-history.yaml --output knowledge/teaagent-history --check
# Keep this docs-only gate runnable in lean local environments. Full test-quality
# collection requires dev extras and should run through its dedicated audit path.
python3 scripts/validate_docs_consistency.py --test-quality-mode off
echo "Docs verification passed."
