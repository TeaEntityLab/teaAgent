"""WS3-002 remaining audit-chain tests for untested functions.

Covers: last_chain_hash(), read_audit_events(), _last_chain_hash_full(),
and verify_audit_chain() strict-mode edge cases.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.audit import AuditLogger
from teaagent.audit_chain import (
    GENESIS_HASH,
    _last_chain_hash_full,
    last_chain_hash,
    read_audit_events,
    verify_audit_chain,
)

# ---------------------------------------------------------------------------
# last_chain_hash() tests
# ---------------------------------------------------------------------------


def test_last_chain_hash_empty_path(tmp_path: Path) -> None:
    """Non-existent log path → returns GENESIS_HASH."""
    result = last_chain_hash(tmp_path / 'nonexistent.jsonl')
    assert result == GENESIS_HASH


def test_last_chain_hash_empty_file(tmp_path: Path) -> None:
    """Zero-byte file → returns GENESIS_HASH."""
    log = tmp_path / 'empty.jsonl'
    log.write_text('', encoding='utf-8')
    result = last_chain_hash(log)
    assert result == GENESIS_HASH


def test_last_chain_hash_single_event(tmp_path: Path) -> None:
    """Single event with hash → returns that hash."""
    log = tmp_path / 'single.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    events = read_audit_events(log)
    expected = events[0]['hash']

    result = last_chain_hash(log)
    assert result == expected
    assert result != GENESIS_HASH


def test_last_chain_hash_multiple_events(tmp_path: Path) -> None:
    """Multiple events → returns last event's hash."""
    log = tmp_path / 'multi.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='first')
    audit.record('iteration_started', 'r1', iteration=1)
    audit.record('run_completed', 'r1', answer='done')

    events = read_audit_events(log)
    expected = events[-1]['hash']

    result = last_chain_hash(log)
    assert result == expected
    assert result != GENESIS_HASH


def test_last_chain_hash_corrupted_last_line(tmp_path: Path) -> None:
    """Corrupted last line (invalid JSON) → skips to previous valid line."""
    log = tmp_path / 'corrupt.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')
    audit.record('run_completed', 'r1', answer='ok')

    # Read the last valid event's hash before corrupting
    events_before = read_audit_events(log)
    expected = events_before[-1]['hash']

    # Append corrupt garbage at end
    with log.open('a', encoding='utf-8') as f:
        f.write('this is not valid json {{{broken\n')

    result = last_chain_hash(log)
    assert result == expected
    assert result != GENESIS_HASH


def test_last_chain_hash_legacy_line(tmp_path: Path) -> None:
    """Legacy line (no hash field) → returns GENESIS_HASH."""
    log = tmp_path / 'legacy.jsonl'
    legacy = {
        'event_id': 'legacy-1',
        'event_type': 'legacy_reset',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    log.write_text(json.dumps(legacy, sort_keys=True) + '\n', encoding='utf-8')

    result = last_chain_hash(log)
    assert result == GENESIS_HASH


# ---------------------------------------------------------------------------
# read_audit_events() tests
# ---------------------------------------------------------------------------


def test_read_audit_events_nonexistent_file(tmp_path: Path) -> None:
    """Non-existent file → returns empty list."""
    result = read_audit_events(tmp_path / 'nonexistent.jsonl')
    assert result == []


def test_read_audit_events_empty_file(tmp_path: Path) -> None:
    """Empty file → returns empty list."""
    log = tmp_path / 'empty.jsonl'
    log.write_text('', encoding='utf-8')
    result = read_audit_events(log)
    assert result == []


def test_read_audit_events_three_valid_events(tmp_path: Path) -> None:
    """Valid JSONL with 3 events → returns 3 dicts."""
    log = tmp_path / 'three.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='first')
    audit.record('iteration_started', 'r1', iteration=1)
    audit.record('run_completed', 'r1', answer='done')

    result = read_audit_events(log)
    assert len(result) == 3
    assert all(isinstance(e, dict) for e in result)
    assert result[0]['event_type'] == 'run_started'
    assert result[-1]['event_type'] == 'run_completed'


def test_read_audit_events_mixed_valid_invalid(tmp_path: Path) -> None:
    """Mixed valid/invalid JSON lines → skips invalid, returns valid."""
    log = tmp_path / 'mixed.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    # Append invalid JSON, then another valid event
    with log.open('a', encoding='utf-8') as f:
        f.write('invalid json line\n')
    audit.record('run_completed', 'r1', answer='ok')

    result = read_audit_events(log)
    assert len(result) == 2
    assert result[0]['event_type'] == 'run_started'
    assert result[1]['event_type'] == 'run_completed'


def test_read_audit_events_non_dict_json(tmp_path: Path) -> None:
    """Non-dict JSON (string, array) → skips non-dict lines."""
    log = tmp_path / 'nondict.jsonl'
    log.write_text(
        json.dumps('just a string')
        + '\n'
        + json.dumps([1, 2, 3])
        + '\n'
        + json.dumps(42)
        + '\n',
        encoding='utf-8',
    )

    result = read_audit_events(log)
    assert result == []


def test_read_audit_events_includes_dicts_only(tmp_path: Path) -> None:
    """Mixed dict + non-dict → only dicts returned."""
    log = tmp_path / 'mixed_nondict.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')

    with log.open('a', encoding='utf-8') as f:
        f.write(json.dumps([1, 2, 3]) + '\n')
        f.write(json.dumps('string value') + '\n')

    audit.record('run_completed', 'r1', answer='ok')

    result = read_audit_events(log)
    assert len(result) == 2  # only the two dict events
    assert result[0]['event_type'] == 'run_started'
    assert result[1]['event_type'] == 'run_completed'


# ---------------------------------------------------------------------------
# _last_chain_hash_full() tests (large file >4096 bytes)
# ---------------------------------------------------------------------------

# _EVENTS_FOR_LARGE_FILE: enough events to guarantee the file exceeds _TAIL_SIZE (4096).
_EVENTS_FOR_LARGE_FILE = 100


def test_last_chain_hash_full_large_file(tmp_path: Path) -> None:
    """File larger than _TAIL_SIZE (4096 bytes) → reads all lines, returns last hash."""
    log = tmp_path / 'large.jsonl'
    audit = AuditLogger(path=log)
    for i in range(_EVENTS_FOR_LARGE_FILE):
        audit.record('test_event', 'r-large', index=i)

    assert log.stat().st_size > 4096, (
        f'File size {log.stat().st_size} bytes, expected > 4096'
    )

    events = read_audit_events(log)
    expected = events[-1]['hash']

    result = _last_chain_hash_full(log)
    assert result == expected
    assert result != GENESIS_HASH


def test_last_chain_hash_full_interleaved_invalid(tmp_path: Path) -> None:
    """Large file with interleaved invalid lines → returns last valid hash."""
    log = tmp_path / 'interleaved.jsonl'
    audit = AuditLogger(path=log)
    for i in range(60):
        audit.record('test_event', 'r-inter', index=i)

    # Append a block of invalid lines in the middle
    with log.open('a', encoding='utf-8') as f:
        for i in range(50):
            f.write(f'invalid garbage data not json {i}\n')

    # Append more valid events at the end
    audit2 = AuditLogger(path=log)
    for i in range(10):
        audit2.record('test_event', 'r-inter-2', index=i)

    events = read_audit_events(log)
    expected = events[-1]['hash']

    result = _last_chain_hash_full(log)
    assert result == expected
    assert result != GENESIS_HASH


def test_last_chain_hash_full_legacy_reset(tmp_path: Path) -> None:
    """Large file with legacy reset at end → returns GENESIS_HASH after reset."""
    log = tmp_path / 'legacy_reset.jsonl'
    audit = AuditLogger(path=log)
    for i in range(60):
        audit.record('test_event', 'r-legacy', index=i)

    # Append a legacy line (no prev_hash/hash fields) at the very end
    legacy = {
        'event_id': 'legacy-reset',
        'event_type': 'legacy',
        'run_id': 'r-legacy',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    with log.open('a', encoding='utf-8') as f:
        f.write(json.dumps(legacy, sort_keys=True) + '\n')

    result = _last_chain_hash_full(log)
    assert result == GENESIS_HASH


def test_last_chain_hash_full_triggers_via_last_chain_hash(tmp_path: Path) -> None:
    """When tail window is all corrupt and file >4KB, last_chain_hash()
    falls through to _last_chain_hash_full and returns the correct hash."""
    log = tmp_path / 'tail_corrupt.jsonl'
    audit = AuditLogger(path=log)
    for i in range(_EVENTS_FOR_LARGE_FILE):
        audit.record('test_event', 'r-tail', index=i)

    events = read_audit_events(log)
    expected = events[-1]['hash']

    # Append enough corrupt lines to fill the tail window (>_TAIL_SIZE)
    # Each corrupt line is ~50 bytes; 100 lines = ~5KB, enough to fill the 4KB tail.
    with log.open('a', encoding='utf-8') as f:
        for i in range(150):
            f.write(f'corrupt garbage {{{{{i}}}}}\n')

    # last_chain_hash reads last 4KB (all corrupt), then falls through
    # to _last_chain_hash_full which scans the entire file.
    result = last_chain_hash(log)
    assert result == expected
    assert result != GENESIS_HASH


# ---------------------------------------------------------------------------
# verify_audit_chain() strict-mode edge cases
# ---------------------------------------------------------------------------


def test_verify_corrupt_jsonl(tmp_path: Path) -> None:
    """Truncated/corrupt JSONL file → not valid, error mentions invalid JSON."""
    log = tmp_path / 'corrupt.jsonl'
    audit = AuditLogger(path=log)
    audit.record('run_started', 'r1', task='test')
    audit.record('run_completed', 'r1', answer='ok')

    # Append a corrupt line
    with log.open('a', encoding='utf-8') as f:
        f.write('this is not valid json {{{broken\n')

    result = verify_audit_chain(log)
    assert not result.valid
    assert result.error is not None
    assert 'invalid json' in result.error.lower()


def test_verify_hmac_without_key_passes(tmp_path: Path) -> None:
    """Log with chain_hmac but verify without key → passes (HMAC not checked)."""
    log = tmp_path / 'hmac_no_key.jsonl'

    # Create log with HMAC-signed entries (AuditLogger always includes chain_hmac)
    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log)
        audit.record('run_started', 'r-hmac', task='hmac-test')

    # Verify without providing a key.  Mock home to a fresh directory so the
    # per-run key file is not found, causing secret_key to stay None and
    # HMAC verification to be skipped.
    clean_home = tmp_path / 'clean'
    clean_home.mkdir()
    with patch.object(Path, 'home', return_value=clean_home):
        result = verify_audit_chain(log)

    assert result.valid, result.error


def test_verify_hmac_wrong_key_fails(tmp_path: Path) -> None:
    """Log with chain_hmac but verify with wrong key → fails."""
    log = tmp_path / 'hmac_wrong.jsonl'

    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log)
        audit.record('run_started', 'r-hmac-wrong', task='hmac-test')

    wrong_key = secrets.token_bytes(32)
    result = verify_audit_chain(log, secret_key=wrong_key)
    assert not result.valid
    assert result.error is not None
    assert 'hmac' in result.error.lower() or 'signature' in result.error.lower()


def test_verify_strict_param_overrides_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """strict=False param overrides TEAAGENT_AUDIT_CHAIN_STRICT=1 env var."""
    monkeypatch.setenv('TEAAGENT_AUDIT_CHAIN_STRICT', '1')
    monkeypatch.setenv('TEAAGENT_AUDIT_CHAIN_LEGACY_COMPAT', '0')

    log = tmp_path / 'env_override.jsonl'
    legacy = {
        'event_id': 'legacy-1',
        'event_type': 'legacy_reset',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    log.write_text(json.dumps(legacy, sort_keys=True) + '\n', encoding='utf-8')

    # Even though env says strict=True, explicit strict=False overrides it.
    # Legacy line is silently skipped rather than rejected.
    result = verify_audit_chain(log, strict=False)
    assert result.valid, result.error


def test_verify_empty_file_valid(tmp_path: Path) -> None:
    """Empty file is trivially valid."""
    log = tmp_path / 'empty.jsonl'
    log.write_text('', encoding='utf-8')
    result = verify_audit_chain(log)
    assert result.valid
    assert result.event_count == 0


def test_verify_nonexistent_file_valid(tmp_path: Path) -> None:
    """Non-existent path is trivially valid."""
    result = verify_audit_chain(tmp_path / 'nonexistent.jsonl')
    assert result.valid
    assert result.event_count == 0
