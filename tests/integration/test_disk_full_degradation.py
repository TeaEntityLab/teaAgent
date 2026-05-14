"""IT: Graceful disk-full degradation in AuditLogger.

When a write raises OSError (e.g. ENOSPC) the logger:
- Does NOT raise or crash the run.
- Continues recording events in memory.
- Records a synthetic _disk_write_error event.
- Exposes the error via the .disk_error property.
- Disables further disk writes to avoid repeated failures.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
from unittest.mock import patch

from teaagent.audit import AuditLogger


def _enospc_write(path: Path, line: str) -> None:
    raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC), str(path))


def test_disk_full_does_not_raise(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)

    with patch('teaagent.audit.append_jsonl_line', side_effect=_enospc_write):
        audit.record('run_started', 'r1', task='hello')  # must not raise

    assert len(audit.events) >= 1


def test_in_memory_events_captured_after_disk_full(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)

    with patch('teaagent.audit.append_jsonl_line', side_effect=_enospc_write):
        audit.record('run_started', 'r1', task='hello')
        audit.record('run_completed', 'r1', answer='ok')

    event_types = [e.event_type for e in audit.events]
    assert 'run_started' in event_types
    assert 'run_completed' in event_types


def test_disk_error_event_recorded(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)

    with patch('teaagent.audit.append_jsonl_line', side_effect=_enospc_write):
        audit.record('run_started', 'r1', task='hello')

    error_events = [e for e in audit.events if e.event_type == '_disk_write_error']
    assert error_events, 'a _disk_write_error event must be recorded'
    assert (
        'ENOSPC' in str(error_events[0].payload).upper()
        or 'space' in str(error_events[0].payload).lower()
        or 'No space' in str(error_events[0].payload)
    )


def test_disk_error_property_set(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)

    with patch('teaagent.audit.append_jsonl_line', side_effect=_enospc_write):
        audit.record('run_started', 'r1', task='hello')

    assert audit.disk_error is not None
    assert isinstance(audit.disk_error, OSError)


def test_disk_error_property_none_on_success(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='hello')
    assert audit.disk_error is None


def test_further_writes_skipped_after_disk_full(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    call_count = {'n': 0}

    def counting_fail(path, line):
        call_count['n'] += 1
        raise OSError(errno.ENOSPC, 'No space left')

    with patch('teaagent.audit.append_jsonl_line', side_effect=counting_fail):
        audit.record('event1', 'r1')
        audit.record('event2', 'r1')
        audit.record('event3', 'r1')

    # Only the first call should have actually tried (once we know disk is full, skip)
    assert call_count['n'] == 1, 'should not retry writes after first ENOSPC'


def test_non_enospc_oserror_also_handled(tmp_path):
    """Any OSError during write should degrade gracefully."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)

    def permission_denied(path, line):
        raise OSError(errno.EACCES, 'Permission denied')

    with patch('teaagent.audit.append_jsonl_line', side_effect=permission_denied):
        audit.record('run_started', 'r1')

    assert audit.disk_error is not None
    assert len(audit.events) >= 1
