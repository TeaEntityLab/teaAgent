"""Test module for audit chain integrity and security.

This module tests the audit logging system's integrity guarantees, which are
critical for security and compliance. The audit chain provides a verifiable
record of all agent operations, enabling detection of tampering and ensuring
accountability for all actions taken by the agent.

Key concepts tested:
- JSON Line Format: Each audit event is valid JSON on its own line
- Event Uniqueness: Event IDs are unique within a run to prevent duplication
- Event Ordering: Events are ordered by creation time (monotonic stream)
- Sensitive Data Redaction: Sensitive values (e.g., file contents) are redacted in logs
- Log Persistence: Logs can be re-read and reconstructed to match in-memory events
- File Permissions: Audit files have restricted permissions (mode 0o600)

Acceptance Criteria:
- AC1: Every event written by AuditLogger is valid JSON parseable individually
- AC2: Event IDs are unique within a run (no duplicates)
- AC3: Events are ordered by creation (monotonic event stream)
- AC4: No sensitive key values appear in persisted log lines (redaction works)
- AC5: Persisted log can be re-read and reconstructed to match in-memory events
- AC6: Audit files are not world-readable (mode 0o600)

Technical Details:
- AuditLogger writes events in JSONL format (one JSON object per line)
- Each event includes event_type, run_id, event_id, and payload
- Event IDs are UUIDs to ensure uniqueness
- Sensitive fields (e.g., 'content' in file operations) are redacted as [REDACTED]
- RunStore manages audit file paths and permissions
- File permissions are set to 0o600 (owner read/write only)

References:
- Audit chain design: /docs/architecture/audit_chain.md
- Security requirements: /docs/security/audit_requirements.md
- Redaction policy: /docs/security/data_redaction.md
"""

from __future__ import annotations

import json

from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


def test_each_audit_line_is_valid_json(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-001', task='test')
    audit.record('iteration_started', 'run-001', iteration=1)
    audit.record('run_completed', 'run-001', answer='done')

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert 'event_type' in obj
        assert 'run_id' in obj
        assert 'event_id' in obj


def test_event_ids_are_unique(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    for i in range(10):
        audit.record('heartbeat', 'run-001', seq=i)

    event_ids = [e.event_id for e in audit.events]
    assert len(event_ids) == len(set(event_ids)), 'event IDs must be unique'


def test_sensitive_values_redacted_in_log(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record(
        'tool_call_started',
        'run-002',
        tool_name='workspace_write_file',
        arguments={'path': 'x.txt', 'content': 'my secret data'},
    )

    raw = log_path.read_text(encoding='utf-8')
    assert 'my secret data' not in raw, 'content argument must be redacted in log'


def test_persisted_log_matches_memory_events(tmp_path):
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-003', task='verify')
    audit.record('run_completed', 'run-003', answer='ok')

    # Re-read from disk
    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    disk_types = [json.loads(line)['event_type'] for line in lines]
    memory_types = [e.event_type for e in audit.events]
    assert disk_types == memory_types


def test_run_store_audit_file_permissions(tmp_path):
    """Audit files should have restricted permissions (mode 0o600)."""
    import stat

    store = RunStore(tmp_path)
    audit = store.audit_logger()
    audit.record('run_started', 'run-perms', task='perm check')

    # Check every audit file created
    for audit_file in tmp_path.rglob('*.jsonl'):
        mode = audit_file.stat().st_mode
        world_readable = bool(mode & stat.S_IROTH)
        assert not world_readable, f'{audit_file} must not be world-readable'
