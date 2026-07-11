# test-type: lifecycle
"""Executable specification for M4 BG-001 background lifecycle acceptance.

Companion to docs/specs/background-lifecycle-acceptance-spec-2026-07-11.md.
Only background lifecycle and the operator cockpit are allowed under the
DR-006 co-maintainer-dogfood carve-out; gateway/cloud work remains held.

The current-state tests pin the persisted record protocol, refusal boundary,
and safe stop reconciliation. The final feature-detection test activates when
background transitions join the ADR-0032 event taxonomy.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from teaagent.ergonomics.background_run import (
    BackgroundRunRecord,
    BackgroundRunStore,
)
from teaagent.runner._events import RunEventType

_RECORD_FIELDS = {
    'background_id',
    'pid',
    'command',
    'started_at',
    'log_path',
    'run_id',
    'label',
    'stopped_at',
    'exit_code',
}


def test_background_record_schema_is_pinned() -> None:
    """BackgroundRunRecord exposes the exact cross-surface protocol fields.

    Attach, list/show, cockpit BackgroundRow conversion, and the BG-001 spec
    all consume this record. Any field addition/removal is a protocol review
    event: update those consumers and the spec in the same change.
    """
    assert {field.name for field in fields(BackgroundRunRecord)} == _RECORD_FIELDS
    record = BackgroundRunRecord(
        background_id='bg-spec',
        pid=123,
        command=['teaagent', 'agent', 'run'],
        started_at='2026-07-11T00:00:00+00:00',
        log_path='/tmp/bg-spec.log',
    )
    assert set(record.to_dict()) == _RECORD_FIELDS
    assert record.run_id is None
    assert record.exit_code is None


def test_start_refuses_empty_command(tmp_path: Path) -> None:
    """Submit rejects an empty command before spawning or persisting a record.

    This is the lifecycle's input boundary: an empty detached process cannot
    produce a run id, audit trail, or terminal receipt. Refusal must leave the
    background directory empty rather than create an orphan immediately.
    """
    store = BackgroundRunStore(tmp_path)
    with pytest.raises(ValueError, match='must not be empty'):
        store.start([])
    assert store.list() == []


def test_lifecycle_roundtrip_exit_then_safe_stop(tmp_path: Path) -> None:
    """A dead persisted process reconciles to terminal state and stops safely.

    Models restart-time observation without launching a real process: a record
    with an impossible pid is loaded, marked not alive, assigned a reconciliation
    timestamp/exit fallback, and stop() converges on a stopped record instead of
    raising. This defends BG-001's idempotent-stop half; audit-based outcome
    reconciliation remains future work described by the companion spec.
    """
    store = BackgroundRunStore(tmp_path)
    log_path = store.dir / 'dead-spec.log'
    log_path.write_text(
        json.dumps({'run_id': 'run-dead-spec', 'status': 'failed'}) + '\n',
        encoding='utf-8',
    )
    record_path = store.dir / 'dead-spec.json'
    record_path.write_text(
        json.dumps(
            {
                'background_id': 'dead-spec',
                'pid': 2_147_483_640,
                'command': ['teaagent', 'agent', 'run'],
                'started_at': '2026-07-11T00:00:00+00:00',
                'log_path': str(log_path),
            }
        ),
        encoding='utf-8',
    )

    observed = store.get('dead-spec')
    assert observed['alive'] is False
    assert observed['run_id'] == 'run-dead-spec'
    assert observed['stopped_at']
    # Cross-process reconciliation may default an unknowable code to zero;
    # the child audit says "failed", so the spec forbids treating this field
    # as authoritative on its own.
    assert observed['exit_code'] == 0

    stopped = store.stop('dead-spec', timeout_seconds=0)
    assert stopped['alive'] is False
    assert stopped['stop_signal'] == 'SIGTERM'
    assert stopped['stopped_at']
    persisted = json.loads(record_path.read_text(encoding='utf-8'))
    assert persisted['stop_signal'] == 'SIGTERM'
    assert 'alive' not in persisted


_HAS_BACKGROUND_EVENT_TAXONOMY = {
    'BACKGROUND_SUBMITTED',
    'BACKGROUND_STOPPED',
}.issubset(RunEventType.__members__)


@pytest.mark.skipif(
    not _HAS_BACKGROUND_EVENT_TAXONOMY,
    reason=(
        'background transition events are not in ADR-0032 taxonomy; see '
        'docs/specs/background-lifecycle-acceptance-spec-2026-07-11.md §3.5'
    ),
)
def test_background_event_taxonomy_activates() -> None:
    """Activation hook for auditable parent-side background transitions.

    Skipped until BG-001 adds BACKGROUND_SUBMITTED/BACKGROUND_STOPPED. Once
    implemented, these values are the stable serialized audit names and the
    promotion checklist must add emitter/reader sequence tests alongside.
    """
    assert (
        RunEventType.__members__['BACKGROUND_SUBMITTED'].value == 'background_submitted'
    )
    assert RunEventType.__members__['BACKGROUND_STOPPED'].value == 'background_stopped'
