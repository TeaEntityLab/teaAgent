"""IT: Audit hash-chain integrity.

Each event persisted by AuditLogger carries a SHA-256 hash of the previous
event (prev_hash) and its own hash.  verify_audit_chain() detects any
tampering, insertion, or deletion.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from teaagent.audit import AuditLogger
from teaagent.audit_chain import (
    GENESIS_HASH,
    ChainVerificationResult,
    verify_audit_chain,
)


def test_clean_log_is_valid(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='hello')
    audit.record('iteration_started', 'r1', iteration=1)
    audit.record('run_completed', 'r1', answer='done')

    result = verify_audit_chain(log)
    assert result.valid, result.error
    assert result.event_count == 3


def test_empty_log_is_valid(tmp_path):
    log = tmp_path / 'empty.jsonl'
    log.write_text('', encoding='utf-8')
    result = verify_audit_chain(log)
    assert result.valid
    assert result.event_count == 0


def test_first_event_prev_hash_is_genesis(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r2', task='genesis check')

    first = json.loads(log.read_text().strip().splitlines()[0])
    assert first['prev_hash'] == GENESIS_HASH


def test_second_event_prev_hash_matches_first(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r3', task='x')
    audit.record('run_completed', 'r3', answer='y')

    lines = log.read_text().strip().splitlines()
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert second['prev_hash'] == first['hash']


def test_content_tampering_detected(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r4', task='tamper')
    audit.record('run_completed', 'r4', answer='ok')

    lines = log.read_text().strip().splitlines()
    obj = json.loads(lines[1])
    obj['event_type'] = 'run_failed'  # tamper the second event
    lines[1] = json.dumps(obj)
    log.write_text('\n'.join(lines), encoding='utf-8')

    result = verify_audit_chain(log)
    assert not result.valid
    assert result.error is not None
    assert 'hash mismatch' in result.error.lower() or 'tampered' in result.error.lower()


def test_event_insertion_detected(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r5', task='insert')
    audit.record('run_completed', 'r5', answer='ok')

    lines = log.read_text().strip().splitlines()
    # Insert a forged event between the two real events with wrong prev_hash
    forged = {
        'event_id': 'fake',
        'event_type': 'forged',
        'run_id': 'r5',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
        'prev_hash': 'wrong',
        'hash': 'alsowrong',
    }
    lines.insert(1, json.dumps(forged))
    log.write_text('\n'.join(lines), encoding='utf-8')

    result = verify_audit_chain(log)
    assert not result.valid


def test_event_deletion_detected(tmp_path):
    log = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r6', task='delete')
    audit.record('iteration_started', 'r6', iteration=1)
    audit.record('run_completed', 'r6', answer='ok')

    lines = log.read_text().strip().splitlines()
    # Remove the middle event — third event's prev_hash will no longer match
    del lines[1]
    log.write_text('\n'.join(lines), encoding='utf-8')

    result = verify_audit_chain(log)
    assert not result.valid


def test_multiple_runs_in_same_log(tmp_path):
    """Two sequential runs in the same log file both form a valid chain."""
    log = tmp_path / 'multi.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'run-A', task='a')
    audit.record('run_completed', 'run-A', answer='done')
    audit.record('run_started', 'run-B', task='b')
    audit.record('run_completed', 'run-B', answer='done')

    result = verify_audit_chain(log)
    assert result.valid
    assert result.event_count == 4


def test_chain_result_type():
    result = ChainVerificationResult(valid=True, event_count=5)
    assert result.valid
    assert result.event_count == 5
    assert result.error is None


# SEC-01: HMAC key persistence across instances


def test_audit_hmac_persisted_across_instances(tmp_path):
    """Two AuditLogger instances for the same run-id load the same persisted key
    so that a second process can verify entries written by the first."""
    log = tmp_path / 'run-sec01.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        audit1 = AuditLogger(path=log)
        audit1.record('run_started', 'r-sec01', task='hmac-persist-test')
        key1 = audit1.get_chain_key()

        # Second instance pointing to the same log — must reload the same key
        audit2 = AuditLogger(path=log)
        key2 = audit2.get_chain_key()

    assert key1 == key2, 'Second instance did not load the persisted key'
    result = verify_audit_chain(log, secret_key=key2)
    assert result.valid, result.error


def test_audit_hmac_fails_with_wrong_key(tmp_path):
    """Verification with the wrong key rejects HMAC-signed entries."""
    log = tmp_path / 'run-wrongkey.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log)
        audit.record('run_started', 'r-wrongkey', task='hmac-reject-test')

    # All-zeros key is deterministic and will not match the random per-run key
    wrong_key = b'\x00' * 32
    result = verify_audit_chain(log, secret_key=wrong_key)
    assert not result.valid, 'Wrong key should cause HMAC verification failure'
    assert result.error is not None
    assert 'hmac' in result.error.lower() or 'signature' in result.error.lower()


def test_audit_key_file_permissions_readable(tmp_path):
    """Key file is persisted with mode 0o600 (owner-only read/write)."""
    log = tmp_path / 'run-keyperm.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        AuditLogger(path=log)
        key_path = tmp_path / '.teaagent' / 'run-keys' / f'{log.stem}.key'

    assert key_path.is_file(), 'HMAC key file was not persisted to disk'
    mode = key_path.stat().st_mode & 0o777
    assert mode == 0o600, (
        f'Key file {key_path} has mode {oct(mode)}, expected 0o600 '
        '(world-readable key file would allow HMAC forgery)'
    )
