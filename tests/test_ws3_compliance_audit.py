"""WS3-001 compliance mode tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.audit import AuditLogger
from teaagent.errors import AuditDurabilityError
from teaagent.security_env import compliance_mode


def test_compliance_mode_env_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('TEAAGENT_COMPLIANCE_MODE', raising=False)
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
