"""Regression contract: audit chain integrity must never be broken.

This is an indestructible contract — if this test fails, the audit log
has lost integrity guarantees that security relies on.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from teaagent.audit import AuditLogger


def test_each_audit_event_has_unique_id(tmp_path: Path) -> None:
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    for i in range(50):
        audit.record('heartbeat', 'run-001', seq=i)

    ids = [e.event_id for e in audit.events]
    assert len(ids) == len(set(ids))


def test_audit_events_append_only(tmp_path: Path) -> None:
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='t')
    audit.record('run_completed', 'run-001', answer='ok')

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert set(obj) >= {'event_id', 'event_type', 'run_id'}


def test_audit_file_permissions_restrictive(tmp_path: Path) -> None:
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='t')

    mode = os.stat(log_path).st_mode & 0o777
    assert mode <= 0o600, f'Audit file mode {oct(mode)} too permissive'


def test_sensitive_values_redacted_in_persisted_log(tmp_path: Path) -> None:
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record(
        'tool_call_started',
        'run-001',
        call_id='c1',
        tool_name='bash',
        arguments={'command': 'echo sk-abcdef1234567890'},
    )

    content = log_path.read_text(encoding='utf-8')
    assert 'sk-abcdef1234567890' not in content
    assert '[redacted]' in content


def test_in_memory_events_match_persisted_log(tmp_path: Path) -> None:
    log_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='test')
    audit.record('run_completed', 'run-001', answer='ok')
    assert len(audit.events) == 2

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 2
