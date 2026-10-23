# test-type: behavior
"""Governance CI jobs run even when the lint job fails."""

from __future__ import annotations

from pathlib import Path

import yaml

_CI = Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'ci.yml'


def _needs(job: dict) -> list[str]:
    needs = job.get('needs')
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    return [str(item) for item in needs]


def test_governance_jobs_are_not_skipped_when_lint_fails() -> None:
    """A red lint job must not skip the governance tier.

    GitHub Actions skips a job when a needed job fails. That is how the
    2026-09-09 config-access ratchet took approval and plan-gate tests dark.
    """
    workflow = yaml.safe_load(_CI.read_text(encoding='utf-8'))
    jobs = workflow['jobs']

    for name in ('governance-gate', 'review-institution'):
        assert 'lint' not in _needs(jobs[name]), name

    package_needs = _needs(jobs['package'])
    assert 'lint' in package_needs
    assert 'governance-gate' in package_needs
