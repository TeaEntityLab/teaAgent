# test-type: behavior
"""Two AuditLogger instances appending to one file must keep one hash chain."""

from __future__ import annotations

from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.audit_chain import verify_audit_chain


def test_second_logger_appends_without_forking_the_chain(tmp_path: Path) -> None:
    """A logger opened first still chains after another logger writes ahead of it."""
    log = tmp_path / 'audit.jsonl'
    first = AuditLogger(path=log)
    second = AuditLogger(path=log)
    assert first._chain_key == second._chain_key

    first.record('run_started', 'run-1', task='opened-before-the-other-write')
    second.record('tool_call_completed', 'run-1', tool='wrote-with-a-stale-cache')
    first.record('run_completed', 'run-1', answer='appended-after-the-other-writer')

    result = verify_audit_chain(log, secret_key=first._chain_key, strict=True)
    assert result.valid, result.error
    assert result.event_count == 3
    assert result.total_prev_hash_mismatches == 0


def test_chain_tip_survives_an_event_larger_than_the_first_read_window(
    tmp_path: Path,
) -> None:
    """The tip read must grow past a partial last line instead of forking."""
    log = tmp_path / 'audit.jsonl'
    writer = AuditLogger(path=log)
    other = AuditLogger(path=log)
    writer.record('run_started', 'run-1', note='x' * 20_000)
    other.record('run_completed', 'run-1', answer='after-large-event')

    result = verify_audit_chain(log, secret_key=writer._chain_key, strict=True)
    assert result.valid, result.error
    assert result.event_count == 2
