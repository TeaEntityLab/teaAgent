"""Lifecycle tests for the EventSpine and RunEvent system.

Tests assert event sequences and interceptor/consumer semantics.
Tests are typed as 'lifecycle' per ADR 0032 §6.
"""

from __future__ import annotations

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
