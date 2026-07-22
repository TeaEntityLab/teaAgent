# test-type: contract
"""Tests for the ADR-0031 H4 decision-packet aggregator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from teaagent.audit import AuditLogger
from teaagent.governance.h4_decision_packet import build_h4_decision_packet
from teaagent.governance.h4_integration import H4GovernanceMode, record_h4_shadow_event

_SCRIPT = 'scripts/build_h4_decision_packet.py'


def _write_matrix(root: Path) -> Path:
    matrix = root / 'docs' / 'architecture' / 'claim-to-test-traceability.yaml'
    matrix.parent.mkdir(parents=True, exist_ok=True)
    matrix.write_text(
        'version: "1"\nclaims: []\nh4_policy_rbac_coverage:\n  policies: []\n  roles: []\n',
        encoding='utf-8',
    )
    return matrix


def _write_audit(root: Path) -> Path:
    log_path = root / '.teaagent' / 'audit.jsonl'
    with patch.object(Path, 'home', return_value=root):
        audit = AuditLogger(path=log_path)
        record_h4_shadow_event(
            audit,
            'run-1',
            surface='approval',
            mode=H4GovernanceMode.SHADOW,
            allowed=False,
            reason='deny writes',
            context={'action': 'approve_tool', 'tool_name': 'write_file'},
            enforced=False,
            details=[],
        )
    return log_path


def test_decision_packet_marks_human_signoff_required(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)
    log_path = _write_audit(tmp_path)

    packet = build_h4_decision_packet(
        tmp_path,
        audit_logs=[log_path],
        matrix_path=matrix,
        iterations=3,
    )
    data = packet.to_dict()

    assert data['promotion_ready'] is False
    assert data['agent_prepared_criteria'] == 4
    assert data['human_required_criteria'] == 1
    statuses = {
        criterion['criterion']: criterion['status'] for criterion in data['criteria']
    }
    assert statuses['1-zero-false-positive-window'] == 'prepared'
    assert statuses['2-coverage-completeness'] == 'prepared'
    assert statuses['3-performance-slo'] == 'prepared'
    assert statuses['4-human-signoff'] == 'human_required'
    assert statuses['5-rollback-plan'] == 'prepared'
    assert data['criteria'][0]['evidence']['candidates'][0]['owner_verdict'] is None


def test_decision_packet_reports_missing_audit_logs(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)

    packet = build_h4_decision_packet(
        tmp_path, audit_logs=[], matrix_path=matrix, iterations=1
    )
    first = packet.to_dict()['criteria'][0]

    assert first['status'] == 'needs_audit_logs'
    assert 'No audit logs' in first['summary']


def test_decision_packet_cli_outputs_json(tmp_path: Path) -> None:
    matrix = _write_matrix(tmp_path)
    log_path = _write_audit(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            _SCRIPT,
            '--root',
            str(tmp_path),
            '--matrix',
            str(matrix),
            '--audit-log',
            str(log_path),
            '--iterations',
            '3',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload['promotion_ready'] is False
    assert payload['human_required_criteria'] == 1


def test_decision_packet_cli_invalid_args() -> None:
    result = subprocess.run(
        [sys.executable, _SCRIPT, '--iterations', '0'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert 'iterations must be > 0' in result.stderr
