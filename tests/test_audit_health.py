"""Tests for teaagent.audit_health (assess_audit_health, format_audit_health, AuditDurabilityHealth)
and SEC-12 3-strikes fsync failure escalation in AuditLogger."""

from __future__ import annotations

import contextlib
import errno
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.audit import AuditLogger
from teaagent.audit_health import (
    AuditDurabilityHealth,
    assess_audit_health,
    format_audit_health,
)
from teaagent.errors import AuditDurabilityError

# ---------------------------------------------------------------------------
# AuditDurabilityHealth.to_dict()
# ---------------------------------------------------------------------------


def test_to_dict_all_fields() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=3,
        chain_valid=True,
        chain_error=None,
        cooldown_active=False,
        event_count=42,
    )
    d = health.to_dict()
    assert d == {
        'disk_write_errors': 3,
        'chain_valid': True,
        'chain_error': None,
        'cooldown_active': False,
        'event_count': 42,
    }
    assert len(d) == 5


def test_to_dict_with_chain_invalid() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=False,
        chain_error='hash mismatch at line 3',
        cooldown_active=True,
        event_count=10,
    )
    d = health.to_dict()
    assert d['chain_valid'] is False
    assert d['chain_error'] == 'hash mismatch at line 3'
    assert d['cooldown_active'] is True


def test_to_dict_with_none_chain() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=None,
        chain_error=None,
        cooldown_active=False,
        event_count=0,
    )
    d = health.to_dict()
    assert d['chain_valid'] is None
    assert d['event_count'] == 0


# ---------------------------------------------------------------------------
# assess_audit_health()
# ---------------------------------------------------------------------------


def test_assess_empty_events_no_logger() -> None:
    """Empty events list, no log_path, no live_logger → all fields correct."""
    health = assess_audit_health([])
    assert health.disk_write_errors == 0
    assert health.chain_valid is None
    assert health.chain_error is None
    assert health.cooldown_active is False
    assert health.event_count == 0


def test_assess_events_with_one_disk_write_error() -> None:
    """Events with one _disk_write_error → disk_write_errors=1."""
    events: list[dict[str, object]] = [
        {'event_type': 'run_started', 'payload': {}},
        {'event_type': '_disk_write_error', 'payload': {'error': 'ENOSPC'}},
        {'event_type': 'run_completed', 'payload': {}},
    ]
    health = assess_audit_health(events)
    assert health.disk_write_errors == 1


def test_assess_events_with_no_disk_write_error() -> None:
    """Events with no _disk_write_error → disk_write_errors=0."""
    events: list[dict[str, object]] = [
        {'event_type': 'run_started', 'payload': {}},
        {'event_type': 'tool_call', 'payload': {'tool': 'read'}},
        {'event_type': 'run_completed', 'payload': {}},
    ]
    health = assess_audit_health(events)
    assert health.disk_write_errors == 0


def test_assess_events_with_multiple_disk_write_errors() -> None:
    """Multiple _disk_write_error events → disk_write_errors counts all."""
    events: list[dict[str, object]] = [
        {'event_type': '_disk_write_error', 'payload': {'error': 'EACCES'}},
        {'event_type': '_disk_write_error', 'payload': {'error': 'ENOSPC'}},
        {'event_type': '_disk_write_error', 'payload': {'error': 'EIO'}},
    ]
    health = assess_audit_health(events)
    assert health.disk_write_errors == 3


def test_assess_with_valid_audit_log(tmp_path: Path) -> None:
    """With log_path pointing to a valid audit log → chain_valid=True."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit.record('run_started', 'r1', task='hello')
    audit.record('tool_call', 'r1', tool='read')
    audit.record('run_completed', 'r1')

    health = assess_audit_health([], log_path=log)
    assert health.chain_valid is True
    assert health.event_count >= 3


def test_assess_with_tampered_audit_log(tmp_path: Path) -> None:
    """With log_path pointing to a tampered audit log → chain_valid=False."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit.record('run_started', 'r1', task='hello')
    audit.record('tool_call', 'r1', tool='read')

    # Tamper: modify a line in the audit log
    lines = log.read_text(encoding='utf-8').splitlines()
    lines[1] = lines[1].replace('"tool_call"', '"SUSPICIOUS_ACTIVITY"')
    log.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    health = assess_audit_health([], log_path=log)
    assert health.chain_valid is False
    assert health.chain_error is not None


def test_assess_with_live_logger_disk_error(tmp_path: Path) -> None:
    """With live_logger that has disk_error set → cooldown_active=True."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)

    # Force a disk error
    with patch(
        'teaagent.audit.os.fsync', side_effect=OSError(errno.ENOSPC, 'No space')
    ):
        audit.record('run_started', 'r1')

    assert audit.disk_error is not None
    health = assess_audit_health([], live_logger=audit)
    assert health.cooldown_active is True


def test_assess_with_live_logger_no_disk_error(tmp_path: Path) -> None:
    """With live_logger that has no disk_error → cooldown_active=False."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit.record('run_started', 'r1')

    assert audit.disk_error is None
    health = assess_audit_health([], live_logger=audit)
    assert health.cooldown_active is False


def test_assess_cooldown_expired(tmp_path: Path) -> None:
    """After cooldown expiry, disk_error property returns None → cooldown_active=False."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    with patch(
        'teaagent.audit.os.fsync', side_effect=OSError(errno.ENOSPC, 'No space')
    ):
        audit.record('run_started', 'r1')

    assert audit.disk_error is not None  # within cooldown

    time.sleep(0.002)  # let cooldown expire
    assert audit.disk_error is None  # cooldown expired

    health = assess_audit_health([], live_logger=audit)
    assert health.cooldown_active is False


# ---------------------------------------------------------------------------
# format_audit_health()
# ---------------------------------------------------------------------------


def test_format_chain_valid() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=True,
        chain_error=None,
        cooldown_active=False,
        event_count=15,
    )
    output = format_audit_health(health)
    assert 'Chain: valid' in output
    assert '15 events' in output


def test_format_chain_invalid() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=False,
        chain_error='hash mismatch at line 2',
        cooldown_active=False,
        event_count=10,
    )
    output = format_audit_health(health)
    assert 'Chain: INVALID' in output
    assert 'hash mismatch at line 2' in output


def test_format_chain_not_verified() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=None,
        chain_error=None,
        cooldown_active=False,
        event_count=0,
    )
    output = format_audit_health(health)
    assert 'Chain: not verified' in output


def test_format_disk_write_errors_present() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=5,
        chain_valid=None,
        chain_error=None,
        cooldown_active=False,
        event_count=100,
    )
    output = format_audit_health(health)
    assert 'Disk write errors' in output
    assert '5' in output  # the count appears


def test_format_cooldown_active() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=None,
        chain_error=None,
        cooldown_active=True,
        event_count=0,
    )
    output = format_audit_health(health)
    assert 'Cooldown: active' in output


def test_format_cooldown_inactive() -> None:
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=None,
        chain_error=None,
        cooldown_active=False,
        event_count=0,
    )
    output = format_audit_health(health)
    assert 'Cooldown: inactive' in output


def test_format_no_disk_errors_no_line() -> None:
    """When disk_write_errors=0, the disk errors line should not appear."""
    health = AuditDurabilityHealth(
        disk_write_errors=0,
        chain_valid=None,
        chain_error=None,
        cooldown_active=False,
        event_count=0,
    )
    output = format_audit_health(health)
    assert 'Disk write errors' not in output


# ---------------------------------------------------------------------------
# SEC-12 3-strikes escalation tests
# ---------------------------------------------------------------------------


def test_three_strikes_raises_audit_durability_error(tmp_path: Path) -> None:
    """3 consecutive fsync failures in non-compliance mode → AuditDurabilityError."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    call_count = [0]

    def fail_thrice(fd: int) -> None:
        call_count[0] += 1
        raise OSError(errno.ENOSPC, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail_thrice):
        # 1st failure — cooldown starts, no raise
        audit.record('event1', 'r1')
        time.sleep(0.002)  # let cooldown expire so retry happens

        # 2nd failure — cooldown again
        audit.record('event2', 'r1')
        time.sleep(0.002)

        # 3rd failure — should raise
        with pytest.raises(
            AuditDurabilityError, match='3 consecutive disk write failures'
        ):
            audit.record('event3', 'r1')

    assert call_count[0] == 3
    # Verify all 3 error events recorded
    error_events = [e for e in audit.events if e.event_type == '_disk_write_error']
    assert len(error_events) == 3


def test_less_than_three_strikes_does_not_raise(tmp_path: Path) -> None:
    """1 or 2 failures in non-compliance mode do NOT raise."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    def fail(fd: int) -> None:
        raise OSError(errno.ENOSPC, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail):
        audit.record('event1', 'r1')  # 1st — no raise
        time.sleep(0.002)
        audit.record('event2', 'r1')  # 2nd — no raise

    # Should not have raised
    assert len(audit.events) >= 2


def test_success_resets_strike_counter(tmp_path: Path) -> None:
    """A successful write resets _consecutive_disk_failures to 0."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    call_count = [0]

    def fail_then_succeed(fd: int) -> None:
        call_count[0] += 1
        if call_count[0] <= 1:
            raise OSError(errno.ENOSPC, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail_then_succeed):
        # 1st call — fails (strikes = 1)
        audit.record('event1', 'r1')
        time.sleep(0.002)

        # 2nd call — succeeds (strikes reset to 0)
        audit.record('event2', 'r1')
        time.sleep(0.002)

        # 3rd call — fails (strikes = 1, NOT 2)
        # Need to change the side_effect to always fail now
        pass

    assert audit._consecutive_disk_failures == 0


def test_success_resets_allow_more_failures(tmp_path: Path) -> None:
    """Fail → success → fail → fail → fail pattern: resets means it takes
    another 3 to trigger escalation (4 failures total, but only 3 consecutive)."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    call_count = [0]

    def fail_succeed_fail_fail_fail(fd: int) -> None:
        call_count[0] += 1
        if call_count[0] == 2:
            return  # success on 2nd call
        raise OSError(errno.ENOSPC, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail_succeed_fail_fail_fail):
        audit.record('event1', 'r1')  # fail → strikes=1
        time.sleep(0.002)

        audit.record('event2', 'r1')  # success → strikes=0 (reset)
        time.sleep(0.002)

        audit.record('event3', 'r1')  # fail → strikes=1
        time.sleep(0.002)

        audit.record('event4', 'r1')  # fail → strikes=2
        time.sleep(0.002)

        with pytest.raises(AuditDurabilityError, match='3 consecutive'):
            audit.record('event5', 'r1')  # fail → strikes=3 → raise


def test_compliance_mode_still_raises_on_first_failure(tmp_path: Path) -> None:
    """Compliance mode behavior unchanged: first OSError still raises AuditDurabilityError."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=True)

    with (
        patch('teaagent.audit.os.fsync', side_effect=OSError(errno.ENOSPC, 'No space')),
        pytest.raises(AuditDurabilityError, match='Audit disk write failed'),
    ):
        audit.record('run_started', 'r1')


def test_three_strikes_critical_error_on_stderr(tmp_path: Path, capsys) -> None:
    """Verify the AUDIT CRITICAL message is printed to stderr on 3rd strike."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    audit._disk_error_cooldown_seconds = 0.001

    def fail(fd: int) -> None:
        raise OSError(errno.ENOSPC, 'No space left on device')

    with patch('teaagent.audit.os.fsync', side_effect=fail):
        audit.record('event1', 'r1')
        time.sleep(0.002)
        audit.record('event2', 'r1')
        time.sleep(0.002)
        with contextlib.suppress(AuditDurabilityError):
            audit.record('event3', 'r1')

    captured = capsys.readouterr()
    assert 'AUDIT CRITICAL' in captured.err
    assert '3 consecutive' in captured.err
    assert 'Halting run' in captured.err


def test_consecutive_disk_failures_initial_value(tmp_path: Path) -> None:
    """_consecutive_disk_failures starts at 0."""
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log, compliance_mode=False)
    assert audit._consecutive_disk_failures == 0
