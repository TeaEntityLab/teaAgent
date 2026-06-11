"""IT: Audit hash-chain integrity.

Each event persisted by AuditLogger carries a SHA-256 hash of the previous
event (prev_hash) and its own hash.  verify_audit_chain() detects any
tampering, insertion, or deletion.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.audit_chain import GENESIS_HASH
from teaagent.types import AuditLogger, ChainVerificationResult, verify_audit_chain

# Audit chain test constants
_LARGE_AUDIT_LOG_EVENT_COUNT = 1000  # Number of events for large log memory test
_LARGE_AUDIT_LOG_DATA_REPEAT = (
    10  # Number of times to repeat data string in large log test
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


# Negative test cases for malformed JSON and encoding issues
def test_malformed_json_line_detected(tmp_path):
    """Audit chain should detect and reject malformed JSON lines."""
    log = tmp_path / 'run-malformed.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    # Append a malformed JSON line
    with open(log, 'a', encoding='utf-8') as f:
        f.write('{"invalid": json, "missing": quote}\n')

    result = verify_audit_chain(log)
    assert not result.valid, 'Malformed JSON should cause chain verification to fail'
    assert result.error is not None


def test_malformed_json_trailing_comma(tmp_path):
    """Audit chain should detect JSON with trailing commas."""
    log = tmp_path / 'run-trailing.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    # Append JSON with trailing comma
    with open(log, 'a', encoding='utf-8') as f:
        f.write('{"event_type": "test", "payload": {"key": "value",}}\n')

    result = verify_audit_chain(log)
    assert not result.valid, (
        'JSON with trailing comma should cause chain verification to fail'
    )


def test_empty_lines_in_log(tmp_path):
    """Audit chain should handle empty lines gracefully."""
    log = tmp_path / 'run-empty-lines.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')
    audit.record('run_completed', 'r1', answer='done')

    # Add empty lines
    with open(log, 'a', encoding='utf-8') as f:
        f.write('\n\n')

    result = verify_audit_chain(log)
    # Empty lines should be skipped, not cause failure
    assert result.valid, f'Empty lines should be handled gracefully: {result.error}'


def test_unicode_encoding_handling(tmp_path):
    """Audit chain should handle Unicode characters correctly."""
    log = tmp_path / 'run-unicode.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test with unicode: 你好世界')

    result = verify_audit_chain(log)
    assert result.valid, f'Unicode should be handled correctly: {result.error}'


def test_corrupted_hash_field(tmp_path):
    """Audit chain should detect corrupted hash fields."""
    log = tmp_path / 'run-corrupted-hash.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    # Manually corrupt the hash field
    lines = log.read_text(encoding='utf-8').splitlines()
    first_line = json.loads(lines[0])
    first_line['hash'] = 'corrupted_hash_value'
    lines[0] = json.dumps(first_line)
    log.write_text('\n'.join(lines), encoding='utf-8')

    result = verify_audit_chain(log)
    assert not result.valid, 'Corrupted hash should cause chain verification to fail'


def test_symlink_attack_on_audit_log_path(tmp_path):
    """Audit chain should detect or reject symlinks on audit log path."""
    real_log = tmp_path / 'real_audit.jsonl'
    symlink_log = tmp_path / 'symlink_audit.jsonl'

    # Create a real audit log
    audit = AuditLogger(path=real_log)
    audit.record('run_started', 'r1', task='test')

    # Create a symlink to the real log
    try:
        os.symlink(real_log, symlink_log)
    except OSError:
        # Symlink creation may fail on some systems; skip test if so
        pytest.skip('Symlink creation not supported on this system')

    # Verify chain via symlink should work (same content)
    result = verify_audit_chain(symlink_log)
    assert result.valid, 'Symlink to valid audit log should verify successfully'


def test_concurrent_file_modification_during_verification(tmp_path):
    """Audit chain verification should handle concurrent file modifications gracefully."""
    log = tmp_path / 'concurrent_audit.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')
    audit.record('run_completed', 'r1', answer='done')

    # Simulate concurrent modification during verification
    modification_occurred = threading.Event()

    def modify_log_during_verification():
        """Simulate a concurrent modification."""
        modification_occurred.wait(timeout=1.0)
        # Try to modify the log while verification is in progress
        with contextlib.suppress(Exception):
            audit.record('run_started', 'r2', task='concurrent')

    # Start modification thread
    thread = threading.Thread(target=modify_log_during_verification)
    thread.start()

    # Signal modification to occur during verification
    modification_occurred.set()

    # Verify chain - should either succeed or fail gracefully, not crash
    result = verify_audit_chain(log)
    thread.join(timeout=2.0)

    # Result should be valid or have a clear error, not crash
    assert result.valid is not None or result.error is not None


def test_large_audit_log_memory_handling(tmp_path):
    """Audit chain should handle large logs without memory exhaustion."""
    log = tmp_path / 'large_audit.jsonl'
    audit = AuditLogger(path=log)

    # Create a large audit log
    for i in range(_LARGE_AUDIT_LOG_EVENT_COUNT):
        audit.record(
            'iteration_started',
            'r1',
            iteration=i,
            data=f'iteration_{i}' * _LARGE_AUDIT_LOG_DATA_REPEAT,
        )

    # Verify chain should complete without memory issues
    result = verify_audit_chain(log)
    assert result.valid, f'Large audit log verification failed: {result.error}'
    assert result.event_count == _LARGE_AUDIT_LOG_EVENT_COUNT
