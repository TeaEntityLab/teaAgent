"""Docs must not drift from pytest-collected acceptance test count."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_VENV_PYTHON = _REPO / '.venv' / 'bin' / 'python'
_ACCEPTANCE_DOC = _REPO / 'docs' / 'acceptance.md'
_ARCHITECTURE_DOC = _REPO / 'docs' / 'architecture.md'
_PYPROJECT = _REPO / 'pyproject.toml'
_ACCEPTANCE_DIR = _REPO / 'tests' / 'acceptance'


def _collect_acceptance_count() -> int:
    # Prefer the repo venv so the acceptance count matches the project docs gate.
    python = str(_VENV_PYTHON if _VENV_PYTHON.exists() else Path(sys.executable))
    result = subprocess.run(
        [python, '-m', 'pytest', str(_ACCEPTANCE_DIR), '--collect-only', '-q'],
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
    count_mentions = re.findall(r'`(\d+)\s+(?:passed|acceptance tests?)`', text)
    assert count_mentions, 'docs/acceptance.md missing an acceptance count marker'
    assert len(count_mentions) == 1, (
        'docs/acceptance.md should keep only the live acceptance count; move '
        'historical counts into dated analysis or roadmap docs'
    )
    doc_count = int(count_mentions[0])
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


def test_full_collection_depends_on_hypothesis_in_dev_dependencies() -> None:
    text = _PYPROJECT.read_text(encoding='utf-8')
    dev_block = re.search(r'(?ms)^dev = \[\n(.*?)^\]', text)
    assert dev_block, 'pyproject.toml missing project.optional-dependencies.dev'
    assert '"hypothesis>=6.100"' in dev_block.group(1), (
        'pyproject.toml should declare hypothesis in project.optional-dependencies.dev '
        'so full pytest collection has the required fuzzing dependency'
    )
