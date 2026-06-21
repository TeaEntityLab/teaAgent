#!/usr/bin/env python3
"""CI gate: validate PR description against review-system.md G2/G4/G9.

Checks:
- G9: PR description contains an action ID (e.g. S-P2-4)
- G2: PR description contains a self-review checklist reference
- G4: High-risk PRs (declared risk class or touching high-risk paths)
      must have docs/reviews/<pr-number>-risk.md

Usage (CI):
    PR_NUMBER=42 PR_BODY="..." PR_BASE_SHA=abc PR_HEAD_SHA=def \
    python3 scripts/check_review_institution_gate.py

Exit codes:
    0 — all gates pass
    1 — one or more gates failed
"""

import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.check_high_risk_paths import high_risk_files, load_patterns  # noqa: E402

ACTION_ID_PATTERN = re.compile(r'\b[SGUA]-P[0-2]-[0-9]\b')
RISK_CLASS_PATTERN = re.compile(r'(?i)risk\s*class[:\s]*(low|medium|high)')
CHECKLIST_PATTERN = re.compile(r'(?i)self.review.checklist|checklist')


def _check_action_id(pr_body: str) -> bool:
    return bool(ACTION_ID_PATTERN.search(pr_body))


def _check_risk_class(pr_body: str) -> str | None:
    match = RISK_CLASS_PATTERN.search(pr_body)
    return match.group(1).lower() if match else None


def _check_self_review(pr_body: str) -> bool:
    return bool(CHECKLIST_PATTERN.search(pr_body))


def _get_pr_diff(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ['git', 'diff', '--name-only', f'{base}..{head}'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.splitlines() if f]


def _touches_high_risk_paths(
    changed_files: list[str], *, config_path: Path | None = None
) -> bool:
    patterns = (
        load_patterns(config_path) if config_path is not None else load_patterns()
    )
    return bool(high_risk_files(changed_files, patterns))


def _has_risk_report(pr_number: str) -> bool:
    if not pr_number:
        return False
    repo_root = Path(__file__).resolve().parent.parent
    risk_report = repo_root / 'docs' / 'reviews' / f'{pr_number}-risk.md'
    return risk_report.is_file()


def main() -> int:
    pr_body = os.environ.get('PR_BODY', '')
    pr_number = os.environ.get('PR_NUMBER', '')
    base = os.environ.get('PR_BASE_SHA', '')
    head = os.environ.get('PR_HEAD_SHA', 'HEAD')

    failures: list[str] = []

    if not _check_action_id(pr_body):
        failures.append(
            'G9: PR description must contain an action ID '
            '(e.g. "Action: S-P2-4") from docs/retrospective/06-action-register.md'
        )

    if not _check_self_review(pr_body):
        failures.append('G2: PR description must reference the self-review checklist')

    risk_class = _check_risk_class(pr_body)
    if not risk_class:
        failures.append(
            'Risk class: PR description must declare risk class (low/medium/high)'
        )

    changed_files = _get_pr_diff(base, head) if base else []
    touches_high_risk = _touches_high_risk_paths(changed_files)
    declared_high = risk_class == 'high'

    if (declared_high or touches_high_risk) and not _has_risk_report(pr_number):
        reason = 'declared as high-risk' if declared_high else 'touches high-risk paths'
        failures.append(
            f'G4: PR {reason} but docs/reviews/{pr_number}-risk.md not found. '
            f'Run the reflective-risk skill and attach the report.'
        )

    if not failures:
        print('OK: Review institution gates pass (G2/G4/G9).')
        if touches_high_risk:
            print('  Note: PR touches high-risk paths; risk report verified.')
        return 0

    print(f'ERROR: {len(failures)} review institution gate failure(s):')
    for f in failures:
        print(f'  {f}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
