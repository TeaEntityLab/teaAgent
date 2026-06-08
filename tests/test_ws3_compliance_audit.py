"""WS3-001 compliance mode tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.security_env import compliance_mode
from teaagent.types import AuditDurabilityError, AuditLogger


def test_compliance_mode_env_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('TEAAGENT_COMPLIANCE_MODE', raising=False)
    assert compliance_mode() is True
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '0')
    assert compliance_mode() is False
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '1')
    assert compliance_mode() is True


def test_compliance_mode_raises_on_disk_write_failure() -> None:
    with TemporaryDirectory() as tmp:
        log = Path(tmp) / 'nested' / 'run.jsonl'
        log.parent.mkdir(parents=True)
        audit = AuditLogger(path=log, compliance_mode=True)
        log.parent.chmod(0o500)
        try:
            with pytest.raises(AuditDurabilityError, match='Audit disk write failed'):
                audit.record('run_started', 'run-1', task='fail closed')
        finally:
            log.parent.chmod(0o755)


def test_non_compliance_mode_continues_in_memory_on_disk_failure() -> None:
    with TemporaryDirectory() as tmp:
        log = Path(tmp) / 'nested' / 'run.jsonl'
        log.parent.mkdir(parents=True)
        audit = AuditLogger(path=log, compliance_mode=False)
        log.parent.chmod(0o500)
        try:
            event = audit.record('run_started', 'run-2', task='best effort')
            assert event.event_type == 'run_started'
            assert len(audit.events) >= 2
            assert audit.disk_error is not None
        finally:
            log.parent.chmod(0o755)


# ---------------------------------------------------------------------------
# WS3-001 edge-case: cooldown expiry retry
# ---------------------------------------------------------------------------


def test_cooldown_expiry_retry_resumes_writes(tmp_path: Path) -> None:
    """After cooldown expires, writes are retried and _disk_write_error
    is NOT recorded for the retried write."""
    import time
    from unittest.mock import patch

    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    call_count = 0

    def fail_first_then_succeed(fd: int) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError(28, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail_first_then_succeed):
        # First write triggers the error → cooldown starts
        audit.record('event1', 'r1')
    # Verify error was recorded
    assert audit.disk_error is not None
    error_events_1 = [e for e in audit.events if e.event_type == '_disk_write_error']
    assert len(error_events_1) == 1

    # Wait for cooldown to expire
    time.sleep(0.01)

    # Second write — should retry and succeed (fsync succeeds now)
    with patch('teaagent.audit.os.fsync', side_effect=fail_first_then_succeed):
        audit.record('event2', 'r1')

    # No NEW _disk_write_error for the retried write
    error_events_2 = [e for e in audit.events if e.event_type == '_disk_write_error']
    assert len(error_events_2) == 1, (
        '_disk_write_error should NOT be recorded for the retried write after cooldown expiry'
    )
    # disk_error should be cleared after successful write
    assert audit.disk_error is None


# ---------------------------------------------------------------------------
# WS3-001 edge-case: env var + param interaction
# ---------------------------------------------------------------------------


def test_compliance_mode_param_overrides_env_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """compliance_mode=True param overrides TEAAGENT_COMPLIANCE_MODE=0 env."""
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '0')
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=True)
    assert audit._compliance_mode is True


def test_compliance_mode_param_overrides_env_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """compliance_mode=False param overrides TEAAGENT_COMPLIANCE_MODE=1 env."""
    monkeypatch.setenv('TEAAGENT_COMPLIANCE_MODE', '1')
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    assert audit._compliance_mode is False


# ---------------------------------------------------------------------------
# WS3-001 edge-case: multiple sink failures
# ---------------------------------------------------------------------------


def test_multiple_sink_failures_handled_cleanly() -> None:
    """Two sinks both raise on sink() — both failures are handled cleanly
    without crashing record()."""
    audit = AuditLogger()  # no path → no disk writes

    sink1_called = False
    sink2_called = False

    def failing_sink1(_event: object) -> None:
        nonlocal sink1_called
        sink1_called = True
        raise RuntimeError('sink1 fail')

    def failing_sink2(_event: object) -> None:
        nonlocal sink2_called
        sink2_called = True
        raise RuntimeError('sink2 fail')

    audit.add_sink(failing_sink1)
    audit.add_sink(failing_sink2)

    # Must not raise
    event = audit.record('run_started', 'r-multi', task='sink bomb')
    assert event.event_type == 'run_started'
    assert sink1_called, 'sink1 should have been called'
    assert sink2_called, 'sink2 should have been called'
    # The event is still recorded in memory regardless of sink failures
    assert audit.events[-1] is event
