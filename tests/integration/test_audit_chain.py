"""IT: Audit hash-chain integrity.

Each event persisted by AuditLogger carries a SHA-256 hash of the previous
event (prev_hash) and its own hash.  verify_audit_chain() detects any
tampering, insertion, or deletion.
"""

from __future__ import annotations

import json

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
