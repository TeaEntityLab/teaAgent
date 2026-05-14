"""AC-NEW-13: Audit log integrity flow.

As a security lead, I want the audit JSONL log to be verifiable so that
any tampering is detectable.

Acceptance criteria:
- Every event written by ``AuditLogger`` is valid JSON parseable individually.
- Event IDs are unique within a run.
- Events are ordered by creation (monotonic event stream).
- No sensitive key values appear in persisted log lines (redaction works).
- Persisted log can be re-read and reconstructed to match in-memory events.
"""

from __future__ import annotations

import json

from teaagent.audit import AuditLogger
from teaagent.run_store import RunStore


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
