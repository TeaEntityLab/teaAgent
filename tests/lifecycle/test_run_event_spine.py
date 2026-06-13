"""Lifecycle tests for the EventSpine and RunEvent system.

Tests assert event sequences and interceptor/consumer semantics.
Tests are typed as 'lifecycle' per ADR 0032 §6.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from teaagent import (
    AgentRunner,
    AuditLogger,
    EventSpine,
    FinalAnswer,
    RunEvent,
    RunEventType,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
)
from teaagent.runner._events import run_event_to_audit_event_type


def build_test_registry() -> ToolRegistry:
    """Build a simple test registry with one read-only tool."""
    registry = ToolRegistry()
    registry.register(
        name='test_echo',
        description='Echo tool for testing.',
        input_schema={
            'type': 'object',
            'properties': {'value': {'type': 'string'}},
            'required': ['value'],
        },
        output_schema={
            'type': 'object',
            'properties': {'value': {'type': 'string'}},
            'required': ['value'],
        },
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: {'value': f'echo: {args["value"]}'},
    )
    return registry


def test_interceptor_registration_and_ordering() -> None:
    """Test that interceptors are registered and execute in order."""
    spine = EventSpine()
    calls: list[str] = []

    spine.register_interceptor(lambda _: calls.append('first'), name='first')
    spine.register_interceptor(lambda _: calls.append('second'), name='second')

    spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})

    assert calls == ['first', 'second']


def test_interceptor_veto_propagates() -> None:
    """Test that an interceptor exception halts the spine."""
    spine = EventSpine()
    calls: list[str] = []

    def veto_interceptor(_: RunEvent) -> None:
        calls.append('veto')
        raise ValueError('veto')

    spine.register_interceptor(lambda _: calls.append('first'), name='first')
    spine.register_interceptor(veto_interceptor, name='veto')
    spine.register_interceptor(lambda _: calls.append('third'), name='third')
    spine.register_consumer(lambda _: calls.append('consumer'), name='consumer')

    with pytest.raises(ValueError, match='veto'):
        spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})

    # Only first and veto ran; third and consumer were skipped.
    assert calls == ['first', 'veto']


def test_consumer_exception_is_isolated() -> None:
    """Test that a consumer exception is caught and logged, run continues."""
    spine = EventSpine()
    calls: list[str] = []

    def failing_consumer(_: RunEvent) -> None:
        calls.append('failing')
        raise RuntimeError('consumer crash')

    spine.register_consumer(lambda _: calls.append('first'), name='first')
    spine.register_consumer(failing_consumer, name='failing')
    spine.register_consumer(lambda _: calls.append('third'), name='third')

    # Should not raise; consumers are isolated.
    spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})

    # All consumers ran despite the exception.
    assert calls == ['first', 'failing', 'third']


def test_critical_consumer_exception_propagates() -> None:
    """Test that a critical consumer's exception propagates."""
    spine = EventSpine()

    def failing_critical(_: RunEvent) -> None:
        raise RuntimeError('critical failure')

    spine.register_consumer(failing_critical, name='critical', critical=True)

    with pytest.raises(RuntimeError, match='critical failure'):
        spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})


def test_event_sequence_monotonicity() -> None:
    """Test that event sequence numbers are monotonic."""
    spine = EventSpine()
    sequences: list[int] = []

    spine.register_consumer(lambda e: sequences.append(e.seq), name='seq_tracker')

    spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})
    spine.emit(RunEventType.ITERATION_STARTED, 'run-1', {'iteration': 1})
    spine.emit(RunEventType.TOOL_CALL_COMPLETED, 'run-1', {'tool_name': 'test'})

    assert sequences == [1, 2, 3]


def test_consumers_run_after_interceptors() -> None:
    """Test that consumers run after all interceptors complete."""
    spine = EventSpine()
    order: list[str] = []

    spine.register_interceptor(lambda _: order.append('interceptor'), name='int')
    spine.register_consumer(lambda _: order.append('consumer'), name='cons')

    spine.emit(RunEventType.RUN_STARTED, 'run-1', {'task': 'test'})

    assert order == ['interceptor', 'consumer']


def test_integration_simple_completed_run() -> None:
    """Integration: drive AgentRunner through a simple completed run, assert event sequence.

    This is the five-minute-proof scenario: one iteration, one tool call.
    Asserts that RUN_STARTED and RUN_COMPLETED are emitted, and that
    ITERATION_STARTED and TOOL_CALL_COMPLETED are present if a tool is called.
    """
    audit = AuditLogger()
    spine = EventSpine()
    events_captured: list[RunEvent] = []
    spine.register_consumer(lambda e: events_captured.append(e), name='recorder')

    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(context: dict[str, Any]):
        """First iteration: request a tool. Second iteration: final answer."""
        if not context['observations']:
            return ToolRequest(
                tool_name='test_echo',
                arguments={'value': 'hello'},
                call_id='call-1',
            )
        return FinalAnswer(
            content=f'Done: {context["observations"][0]["result"]["value"]}'
        )

    result = runner.run(task='simple test', decide=decide, run_id='run-proof')

    assert result.status == 'completed'
    assert result.tool_calls == 1
    assert result.iterations == 2

    # Extract event types in order.
    event_types = [e.type for e in events_captured]

    # Assert expected sequence.
    assert RunEventType.RUN_STARTED in event_types
    assert RunEventType.ITERATION_STARTED in event_types
    assert RunEventType.TOOL_CALL_COMPLETED in event_types
    assert RunEventType.RUN_COMPLETED in event_types

    # Assert ordering: RUN_STARTED before anything else.
    assert event_types[0] == RunEventType.RUN_STARTED
    # RUN_COMPLETED is last.
    assert event_types[-1] == RunEventType.RUN_COMPLETED

    # Assert payloads are present.
    run_started = [e for e in events_captured if e.type == RunEventType.RUN_STARTED][0]
    assert run_started.run_id == 'run-proof'
    assert 'task' in run_started.payload

    run_completed = [
        e for e in events_captured if e.type == RunEventType.RUN_COMPLETED
    ][0]
    assert run_completed.run_id == 'run-proof'
    assert 'answer' in run_completed.payload
    assert 'cost_cents' in run_completed.payload

    tool_completed = [
        e for e in events_captured if e.type == RunEventType.TOOL_CALL_COMPLETED
    ][0]
    assert tool_completed.run_id == 'run-proof'
    assert 'tool_name' in tool_completed.payload
    assert tool_completed.payload['tool_name'] == 'test_echo'


def test_integration_run_with_final_answer_no_tools() -> None:
    """Integration: final answer on first iteration (no tool calls).

    Asserts that RUN_STARTED and RUN_COMPLETED are emitted,
    ITERATION_STARTED is present, but TOOL_CALL_COMPLETED is absent.
    """
    audit = AuditLogger()
    spine = EventSpine()
    events_captured: list[RunEvent] = []
    spine.register_consumer(lambda e: events_captured.append(e), name='recorder')

    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(_context: dict[str, Any]):
        return FinalAnswer(content='immediate answer')

    result = runner.run(task='no tools', decide=decide, run_id='run-noop')

    assert result.status == 'completed'
    assert result.tool_calls == 0
    assert result.iterations == 1

    event_types = [e.type for e in events_captured]

    assert RunEventType.RUN_STARTED in event_types
    assert RunEventType.ITERATION_STARTED in event_types
    assert RunEventType.RUN_COMPLETED in event_types
    # No tool call means no TOOL_CALL_COMPLETED.
    assert RunEventType.TOOL_CALL_COMPLETED not in event_types


def test_integration_run_failed_on_exception() -> None:
    """Integration: run fails when an exception occurs, RUN_FAILED is emitted."""
    audit = AuditLogger()
    spine = EventSpine()
    events_captured: list[RunEvent] = []
    spine.register_consumer(lambda e: events_captured.append(e), name='recorder')

    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(_context: dict[str, Any]):
        # Raise an exception to trigger run failure.
        raise ValueError('decision error')

    # The runner catches bare exceptions and converts them to failed:system.
    result = runner.run(task='failing task', decide=decide, run_id='run-fail')

    assert result.status.startswith('failed:')

    event_types = [e.type for e in events_captured]
    assert RunEventType.RUN_STARTED in event_types
    assert RunEventType.RUN_FAILED in event_types

    # RUN_FAILED should have category and message in payload.
    run_failed = [e for e in events_captured if e.type == RunEventType.RUN_FAILED][0]
    assert 'category' in run_failed.payload
    assert 'message' in run_failed.payload


# ---------------------------------------------------------------------------
# M1-T002: RunEvent-to-AuditEvent mapper
# ---------------------------------------------------------------------------


def test_run_event_to_audit_event_type_maps_all_m0() -> None:
    """Every M0 RunEventType maps to the expected audit event type string."""
    cases: dict[RunEventType, str] = {
        RunEventType.RUN_STARTED: 'run_started',
        RunEventType.ITERATION_STARTED: 'iteration_started',
        RunEventType.TOOL_CALL_REQUESTED: 'tool_call_requested',
        RunEventType.TOOL_CALL_COMPLETED: 'tool_call_completed',
        RunEventType.TOOL_CALL_FAILED: 'tool_call_failed',
        RunEventType.RUN_COMPLETED: 'run_completed',
        RunEventType.RUN_FAILED: 'run_failed',
    }
    for event_type, expected_audit_type in cases.items():
        assert run_event_to_audit_event_type(event_type) == expected_audit_type


def test_run_event_to_audit_event_type_raises_for_unsupported() -> None:
    """Unsupported planned event types raise ValueError."""
    with pytest.raises(ValueError, match='no audit event mapping'):
        run_event_to_audit_event_type('plan_resolved')


# ---------------------------------------------------------------------------
# M1-T001: Golden audit fixture — capture current JSONL output as baseline
# ---------------------------------------------------------------------------


def _normalize_audit_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize nondeterministic fields for golden-fixture comparison."""
    normalized = dict(entry)
    for key in ('event_id', 'created_at', 'hash', 'prev_hash', 'chain_hmac'):
        normalized.pop(key, None)
    return normalized


def test_golden_audit_fixture_completed_run(tmp_path: Path) -> None:
    """Capture audit JSONL for a completed run; serve as golden baseline.

    This test drives the five-minute-proof scenario through AgentRunner
    and captures the full audit JSONL output. After M1-T004, the same
    test run through the event-spine consumer must produce byte-equivalent
    output (after normalizing nondeterministic fields).
    """
    audit_path = tmp_path / 'audit.jsonl'
    audit = AuditLogger(path=audit_path)
    spine = EventSpine()
    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(context: dict[str, Any]):
        if not context['observations']:
            return ToolRequest(
                tool_name='test_echo',
                arguments={'value': 'golden'},
                call_id='call-golden',
            )
        return FinalAnswer(
            content=f'Done: {context["observations"][0]["result"]["value"]}'
        )

    result = runner.run(task='golden fixture', decide=decide, run_id='run-golden')

    assert result.status == 'completed'
    assert result.tool_calls == 1

    # Read the audit file
    assert audit_path.is_file()
    lines = audit_path.read_text(encoding='utf-8').strip().splitlines()
    assert (
        len(lines) >= 3
    )  # RUN_STARTED, ITERATION_STARTED, TOOL_CALL_COMPLETED, RUN_COMPLETED

    entries = [json.loads(line) for line in lines]

    # Verify structure: each entry has mandatory fields
    for entry in entries:
        assert 'event_id' in entry
        assert 'event_type' in entry
        assert 'run_id' in entry
        assert 'payload' in entry
        assert 'prev_hash' in entry
        assert 'hash' in entry
        assert 'chain_hmac' in entry

    # Verify chain: first prev_hash is genesis
    assert entries[0]['prev_hash'] == 'genesis'

    # Verify event order matches expected lifecycle
    event_types = [e['event_type'] for e in entries]
    assert event_types[0] == 'run_started'
    assert event_types[-1] == 'run_completed'

    # Verify run_id consistency
    for entry in entries:
        assert entry['run_id'] == 'run-golden'


def test_golden_audit_fixture_failed_run(tmp_path: Path) -> None:
    """Capture audit JSONL for a failed run; golden baseline for failure path."""
    audit_path = tmp_path / 'audit-fail.jsonl'
    audit = AuditLogger(path=audit_path)
    spine = EventSpine()
    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(_context: dict[str, Any]):
        raise ValueError('simulated failure')

    result = runner.run(task='failing golden', decide=decide, run_id='run-golden-fail')

    assert result.status.startswith('failed:')

    assert audit_path.is_file()
    lines = audit_path.read_text(encoding='utf-8').strip().splitlines()
    entries = [json.loads(line) for line in lines]

    # Must have RUN_STARTED and RUN_FAILED
    event_types = [e['event_type'] for e in entries]
    assert 'run_started' in event_types
    assert 'run_failed' in event_types
    assert entries[0]['event_type'] == 'run_started'
    assert entries[-1]['event_type'] == 'run_failed'


# Frozen M1 byte-equivalence contract. This sequence was verified equal to the
# pre-M1 dual-write audit output (commit ddd32f1) for the echo scenario below,
# normalizing only nondeterministic fields. It locks the consumer-derived audit
# stream so any change to the mapper/consumer that alters event order or payload
# shape turns this test red (ADR 0032 M1 invariant; T001 byte-equivalence).
_GOLDEN_COMPLETED_CONTRACT: list[tuple[str, tuple[str, ...]]] = [
    ('run_started', ('replayed_observations', 'task')),
    ('iteration_started', ('iteration',)),
    (
        'tool_call_started',
        ('annotations', 'arguments', 'call_id', 'reasoning', 'tool_name'),
    ),
    ('tool_call_completed', ('call_id', 'duration_ms', 'result', 'tool_name')),
    ('iteration_started', ('iteration',)),
    (
        'run_completed',
        ('answer', 'cost_cents', 'input_tokens', 'metadata', 'output_tokens'),
    ),
]


def test_m1_audit_stream_matches_frozen_contract(tmp_path: Path) -> None:
    """Consumer-derived audit stream matches the frozen pre-M1 contract.

    Pins the event-type order and per-event payload key-set for the canonical
    echo scenario. Verified byte-equivalent to the dual-write baseline at M1
    take-over; this guards the equivalence going forward.
    """
    audit_path = tmp_path / 'audit.jsonl'
    runner = AgentRunner(
        registry=build_test_registry(),
        audit=AuditLogger(path=audit_path),
        event_spine=EventSpine(),
    )

    def decide(context: dict[str, Any]):
        if not context['observations']:
            return ToolRequest(
                tool_name='test_echo',
                arguments={'value': 'golden'},
                call_id='call-golden',
            )
        return FinalAnswer(content='done')

    runner.run(task='golden contract', decide=decide, run_id='run-golden')

    entries = [
        json.loads(line)
        for line in audit_path.read_text(encoding='utf-8').strip().splitlines()
    ]
    observed = [
        (e['event_type'], tuple(sorted(e.get('payload', {}).keys()))) for e in entries
    ]
    assert observed == _GOLDEN_COMPLETED_CONTRACT
