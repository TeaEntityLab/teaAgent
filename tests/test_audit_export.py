from __future__ import annotations

import json
import tempfile
from pathlib import Path

from teaagent.audit_export import (
    export_compliance_bundle,
    verify_bundle_integrity,
    write_compliance_bundle,
)


def test_export_empty_events():
    bundle = export_compliance_bundle([])
    assert bundle['event_count'] == 0
    assert bundle['version'] == 1
    assert bundle['run_id'] is None
    assert bundle['signed_digest'] is not None


def test_export_non_empty_events():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {'task': 'test'},
            'prev_hash': 'genesis',
            'hash': 'abc123',
        },
        {
            'event_id': 'e2',
            'event_type': 'run_completed',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:01:00Z',
            'payload': {'status': 'ok'},
            'prev_hash': 'abc123',
            'hash': 'def456',
        },
    ]
    bundle = export_compliance_bundle(events, run_id='r1')
    assert bundle['event_count'] == 2
    assert bundle['run_id'] == 'r1'
    assert bundle['summary']['tool_calls_started'] == 0
    assert len(bundle['events']) == 2


def test_export_chain_verification_with_log_path():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
            'prev_hash': 'genesis',
            'hash': 'abc',
        },
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(events[0]) + '\n')
        log_path = Path(f.name)

    try:
        bundle = export_compliance_bundle(
            events, include_chain_verification=True, log_path=log_path
        )
        assert bundle['chain_verification'] is not None
        assert isinstance(bundle['chain_verification']['valid'], bool)
    finally:
        log_path.unlink(missing_ok=True)


def test_export_chain_verification_no_log_path():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
        },
    ]
    bundle = export_compliance_bundle(events, include_chain_verification=True)
    assert bundle['chain_verification'] is None


def test_export_chain_verification_disabled():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
        },
    ]
    bundle = export_compliance_bundle(events, include_chain_verification=False)
    assert bundle['chain_verification'] is None


def test_write_compliance_bundle():
    bundle = export_compliance_bundle([])
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / 'compliance.json'
        result = write_compliance_bundle(bundle, out_path)
        assert result == out_path
        assert out_path.exists()
        loaded = json.loads(out_path.read_text(encoding='utf-8'))
        assert loaded['version'] == 1


def test_verify_bundle_integrity_valid():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
        },
    ]
    bundle = export_compliance_bundle(events)
    assert verify_bundle_integrity(bundle) is True


def test_verify_bundle_integrity_tampered():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
        },
    ]
    bundle = export_compliance_bundle(events)
    bundle['event_count'] = 999
    assert verify_bundle_integrity(bundle) is False


def test_verify_bundle_missing_digest():
    assert verify_bundle_integrity({}) is False
    assert verify_bundle_integrity({'version': 1}) is False


def test_export_summary_tool_call_counts():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'tool_call_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
        },
        {
            'event_id': 'e2',
            'event_type': 'tool_call_completed',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:01Z',
            'payload': {},
        },
        {
            'event_id': 'e3',
            'event_type': 'tool_call_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:02Z',
            'payload': {},
        },
        {
            'event_id': 'e4',
            'event_type': 'tool_call_failed',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:03Z',
            'payload': {},
        },
        {
            'event_id': 'e5',
            'event_type': 'tool_call_blocked',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:04Z',
            'payload': {},
        },
    ]
    bundle = export_compliance_bundle(events)
    assert bundle['summary']['tool_calls_started'] == 2
    assert bundle['summary']['tool_calls_completed'] == 1
    assert bundle['summary']['tool_calls_failed'] == 1
    assert bundle['summary']['tool_calls_blocked'] == 1


def test_export_summary_time_range():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
        },
        {
            'event_id': 'e2',
            'event_type': 'run_completed',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:05:00Z',
            'payload': {},
        },
    ]
    bundle = export_compliance_bundle(events)
    assert bundle['summary']['time_range']['earliest'] == '2026-01-01T00:00:00Z'
    assert bundle['summary']['time_range']['latest'] == '2026-01-01T00:05:00Z'


def test_export_summary_time_range_single_event():
    events = [
        {
            'event_id': 'e1',
            'event_type': 'run_started',
            'run_id': 'r1',
            'created_at': '2026-01-01T00:00:00Z',
            'payload': {},
        },
    ]
    bundle = export_compliance_bundle(events)
    assert bundle['summary']['time_range']['earliest'] == '2026-01-01T00:00:00Z'
    assert bundle['summary']['time_range']['latest'] == '2026-01-01T00:00:00Z'


def test_write_compliance_bundle_compact():
    bundle = export_compliance_bundle([])
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / 'compact.json'
        write_compliance_bundle(bundle, out_path, pretty=False)
        text = out_path.read_text(encoding='utf-8')
        assert '\n' not in text.strip()
