#!/usr/bin/env python3
"""Pre-commit gate: high-risk path changes require a reflective-risk report.

review-system.md §4.2 / G4: when staged files touch a high-risk path (listed in
``scripts/high_risk_paths.yaml`` — the single source shared with the CI
review-institution-gate), the change must be accompanied by a reflective-risk
report at ``docs/reviews/<id>-risk.md``, or explicitly acknowledged.

The gate passes when ANY of:
  - no staged file matches a high-risk pattern;
  - a ``docs/reviews/*-risk.md`` file is staged in the same commit;
  - ``TEAAGENT_RISK_ACK`` is set (records an explicit acknowledgement reason),
    mirroring the repo's ``ALLOW_TEST_WEAKENING`` escape-hatch convention.

Usage:
    python3 scripts/check_high_risk_paths.py

Exit codes:
    0 — no high-risk change, or one with a risk report / acknowledgement
    1 — high-risk path staged without a reflective-risk report
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _REPO_ROOT / 'scripts' / 'high_risk_paths.yaml'
_RISK_REPORT_GLOB = 'docs/reviews/*-risk.md'


def load_patterns(config_path: Path = _CONFIG) -> list[str]:
    """Load high-risk path patterns from the shared YAML config."""
    data = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
    return [str(p) for p in data.get('patterns', [])]


def path_matches(path: str, pattern: str) -> bool:
    """Match a repo-relative path against one high-risk pattern.

    Patterns ending in ``/`` are directory prefixes (any file beneath); all
    others are fnmatch globs (e.g. ``teaagent/approval_*.py``).
    """
    if pattern.endswith('/'):
        return path == pattern.rstrip('/') or path.startswith(pattern)
    return fnmatch.fnmatch(path, pattern)


def high_risk_files(staged: list[str], patterns: list[str]) -> list[str]:
    """Return the staged files that match any high-risk pattern."""
    return [f for f in staged if any(path_matches(f, p) for p in patterns)]


def has_risk_report(staged: list[str]) -> bool:
    """Whether a reflective-risk report is staged in this commit."""
    return any(fnmatch.fnmatch(f, _RISK_REPORT_GLOB) for f in staged)


def _staged_files() -> list[str]:
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    patterns = load_patterns()
    staged = _staged_files()
    matched = high_risk_files(staged, patterns)
    if not matched:
        return 0

    if has_risk_report(staged):
        return 0

    ack = os.environ.get('TEAAGENT_RISK_ACK')
    if ack:
        print(f'high-risk paths acknowledged (TEAAGENT_RISK_ACK={ack!r}):')
        for f in matched:
            print(f'  - {f}')
        return 0

    print('❌ High-risk path(s) staged without a reflective-risk report (G4):')
    for f in matched:
        print(f'  - {f}')
    print()
    print('review-system.md §4.2: changes to approval / policy / audit / sandbox /')
    print('budget / runner gates require a reflective-risk report. Either:')
    print('  - run the reflective-risk skill and stage docs/reviews/<id>-risk.md, or')
    print('  - set TEAAGENT_RISK_ACK="<reason>" to acknowledge (recorded in output).')
    return 1


if __name__ == '__main__':
    sys.exit(main())
