# test-type: contract
"""Tests for ADR-0031 H4 rollback dry-run evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from teaagent.governance.h4_rollback import run_h4_rollback_dry_run

_SCRIPT = 'scripts/verify_h4_rollback.py'


def test_h4_rollback_dry_run_proves_shadow_proceeds_and_not_enforced() -> None:
    report = run_h4_rollback_dry_run()

    assert report.ok is True
    assert report.policy.proceeded is True
    assert report.policy.mode == 'shadow'
    assert report.policy.allowed is False
    assert report.policy.enforced is False
    assert report.rbac.proceeded is True
    assert report.rbac.mode == 'shadow'
    assert report.rbac.allowed is False
    assert report.rbac.enforced is False
    assert 'process-local env vars' in report.to_dict()['note']


def test_h4_rollback_dry_run_restores_env_vars(monkeypatch) -> None:
    monkeypatch.setenv('TEAAGENT_H4_POLICY_MODE', 'enforce')
    monkeypatch.setenv('TEAAGENT_H4_RBAC_MODE', 'enforce')

    report = run_h4_rollback_dry_run()

    assert report.ok is True
    assert os.environ['TEAAGENT_H4_POLICY_MODE'] == 'enforce'
    assert os.environ['TEAAGENT_H4_RBAC_MODE'] == 'enforce'


def test_h4_rollback_cli_outputs_ok_report() -> None:
    result = subprocess.run(
        [sys.executable, _SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload['ok'] is True
    assert payload['policy']['mode'] == 'shadow'
    assert payload['rbac']['mode'] == 'shadow'
    assert payload['policy']['enforced'] is False
    assert payload['rbac']['enforced'] is False
