"""Docs must not drift from pytest-collected acceptance test count."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ACCEPTANCE_DOC = _REPO / 'docs' / 'acceptance.md'
_ARCHITECTURE_DOC = _REPO / 'docs' / 'architecture.md'
_ACCEPTANCE_DIR = _REPO / 'tests' / 'acceptance'


def _collect_acceptance_count() -> int:
    result = subprocess.run(
        ['python3', '-m', 'pytest', str(_ACCEPTANCE_DIR), '--collect-only', '-q'],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO,
    )
    output = f'{result.stdout}\n{result.stderr}'
    match = re.search(r'(\d+)\s+tests?\s+collected', output)
    assert match, f'Could not parse pytest collection output:\n{output}'
    return int(match.group(1))


def test_acceptance_doc_passed_count_matches_pytest_collect() -> None:
    text = _ACCEPTANCE_DOC.read_text(encoding='utf-8')
    doc_match = re.search(r'`(\d+)\s+passed`', text)
    assert doc_match, "docs/acceptance.md missing '`N passed`' status marker"
    doc_count = int(doc_match.group(1))
    collected = _collect_acceptance_count()
    assert doc_count == collected, (
        f'docs/acceptance.md says {doc_count} passed but pytest collects {collected} '
        'acceptance tests — run: python3 scripts/build_acceptance_status.py --source collect'
    )


def test_architecture_matrix_avoids_stale_acceptance_counts() -> None:
    text = _ARCHITECTURE_DOC.read_text(encoding='utf-8')
    assert '104+' not in text
    assert re.search(r'10[0-3]\+\s*AT', text) is None
    assert 'docs/acceptance.md' in text or 'pytest-collected' in text.lower()
