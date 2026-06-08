"""WS3-002 strict audit-chain verification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teaagent.security_env import audit_chain_legacy_compat, audit_chain_strict
from teaagent.types import AuditLogger, verify_audit_chain


def test_strict_mode_rejects_legacy_reset_line(tmp_path: Path) -> None:
    log = tmp_path / 'mixed.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='chained')
    legacy = {
        'event_id': 'legacy-1',
        'event_type': 'legacy_reset',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    with log.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(legacy) + '\n')

    result = verify_audit_chain(log, strict=True, allow_legacy_reset=False)
    assert not result.valid
    assert result.error is not None
    assert 'legacy event' in result.error


def test_strict_mode_allows_legacy_with_compat_flag(tmp_path: Path) -> None:
    log = tmp_path / 'legacy-only.jsonl'
    legacy = {
        'event_id': 'legacy-1',
        'event_type': 'legacy_reset',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    log.write_text(json.dumps(legacy) + '\n', encoding='utf-8')

    result = verify_audit_chain(log, strict=True, allow_legacy_reset=True)
    assert result.valid, result.error


def test_audit_chain_env_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('TEAAGENT_AUDIT_CHAIN_STRICT', raising=False)
    monkeypatch.delenv('TEAAGENT_AUDIT_CHAIN_LEGACY_COMPAT', raising=False)
    assert audit_chain_strict() is False
    assert audit_chain_legacy_compat() is True
    monkeypatch.setenv('TEAAGENT_AUDIT_CHAIN_STRICT', 'yes')
    monkeypatch.setenv('TEAAGENT_AUDIT_CHAIN_LEGACY_COMPAT', '0')
    assert audit_chain_strict() is True
    assert audit_chain_legacy_compat() is False
