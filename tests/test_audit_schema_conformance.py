"""G-P0-1 (ADR-0039): audit schema conformance tests.

Validates that sample chained audit events written by ``AuditLogger``
conform to both the logical event schema
(``docs/audit-event.schema.json``) and the strict chain-entry envelope
schema (``docs/audit-chain-entry.schema.json``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator

from teaagent.types import AuditLogger

SCHEMA_DIR = Path(__file__).resolve().parent.parent / 'docs'
EVENT_SCHEMA_PATH = SCHEMA_DIR / 'audit-event.schema.json'
CHAIN_ENTRY_SCHEMA_PATH = SCHEMA_DIR / 'audit-chain-entry.schema.json'


@pytest.fixture(scope='module')
def event_schema() -> dict:
    return json.loads(EVENT_SCHEMA_PATH.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def chain_entry_schema() -> dict:
    return json.loads(CHAIN_ENTRY_SCHEMA_PATH.read_text(encoding='utf-8'))


def _write_sample_chained_events(tmp_path: Path) -> Path:
    """Write a small chained audit log via AuditLogger and return its path."""
    log_path = tmp_path / 'conformance.jsonl'
    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log_path)
        audit.record('run_started', 'r-conf', task='schema conformance test')
        audit.record('tool_call_completed', 'r-conf', tool_name='dummy', call_id='c1')
        audit.record('run_completed', 'r-conf', answer={'content': 'done'})
    return log_path


def _read_events(log_path: Path) -> list[dict]:
    events: list[dict] = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def test_chained_events_conform_to_logical_event_schema(
    tmp_path: Path, event_schema: dict
) -> None:
    """Every chained event validates against the logical event schema."""
    log_path = _write_sample_chained_events(tmp_path)
    events = _read_events(log_path)
    assert len(events) >= 3

    validator = Draft202012Validator(event_schema)
    for event in events:
        errors = sorted(validator.iter_errors(event), key=lambda e: e.message)
        assert not errors, (
            f'event {event.get("event_id")} failed logical schema: '
            f'{[e.message for e in errors]}'
        )


def test_chained_events_conform_to_chain_entry_envelope(
    tmp_path: Path, chain_entry_schema: dict
) -> None:
    """Every chained event validates against the strict chain-entry envelope."""
    log_path = _write_sample_chained_events(tmp_path)
    events = _read_events(log_path)
    assert len(events) >= 3

    validator = Draft202012Validator(chain_entry_schema)
    for event in events:
        errors = sorted(validator.iter_errors(event), key=lambda e: e.message)
        assert not errors, (
            f'event {event.get("event_id")} failed chain-entry envelope: '
            f'{[e.message for e in errors]}'
        )


def test_chain_entry_envelope_rejects_unknown_field(
    chain_entry_schema: dict,
) -> None:
    """additionalProperties:false rejects unexpected envelope fields."""
    validator = Draft202012Validator(chain_entry_schema)
    bad_event = {
        'event_id': 'e1',
        'event_type': 'test',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
        'prev_hash': 'genesis',
        'hash': 'abc',
        'chain_hmac': 'def',
        'unexpected_field': 'boom',
    }
    errors = list(validator.iter_errors(bad_event))
    assert any(
        'unexpected_field' in str(e) or 'additional' in e.message.lower()
        for e in errors
    ), f'expected additionalProperties rejection, got: {[e.message for e in errors]}'


def test_logical_event_schema_allows_extra_fields(event_schema: dict) -> None:
    """additionalProperties:true permits physical envelope fields."""
    validator = Draft202012Validator(event_schema)
    physical_event = {
        'event_id': 'e1',
        'event_type': 'run_started',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {'task': 'x'},
        'prev_hash': 'genesis',
        'hash': 'abc',
        'chain_hmac': 'def',
    }
    errors = list(validator.iter_errors(physical_event))
    assert not errors, f'physical event should validate: {[e.message for e in errors]}'


def test_chain_entry_envelope_requires_integrity_fields(
    chain_entry_schema: dict,
) -> None:
    """The envelope requires prev_hash, hash, and chain_hmac."""
    validator = Draft202012Validator(chain_entry_schema)
    missing_integrity = {
        'event_id': 'e1',
        'event_type': 'test',
        'run_id': 'r1',
        'created_at': '2026-01-01T00:00:00+00:00',
        'payload': {},
    }
    errors = list(validator.iter_errors(missing_integrity))
    required_missing = {
        prop
        for err in errors
        for prop in ('prev_hash', 'hash', 'chain_hmac')
        if prop in err.message
    }
    assert required_missing == {'prev_hash', 'hash', 'chain_hmac'}, (
        f'expected prev_hash/hash/chain_hmac required failures, '
        f'got: {[e.message for e in errors]}'
    )
