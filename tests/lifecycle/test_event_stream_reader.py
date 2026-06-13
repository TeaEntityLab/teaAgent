"""Lifecycle tests for the Event Stream Reader.

Tests assert that audit JSONL entries can be read as typed RunEvents,
with proper mapping, sequencing, and redaction preservation.
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
    RunEventType,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
    audit_event_to_run_event_type,
    read_run_events_from_audit,
    read_run_events_from_jsonl,
)


def test_audit_event_to_run_event_type_m0_events() -> None:
    """Test that each M0 audit event string maps back to the correct RunEventType."""
    # Each M0 event type should map back
    assert audit_event_to_run_event_type('run_started') == RunEventType.RUN_STARTED
    assert (
        audit_event_to_run_event_type('iteration_started')
        == RunEventType.ITERATION_STARTED
    )
    assert (
        audit_event_to_run_event_type('tool_call_requested')
        == RunEventType.TOOL_CALL_REQUESTED
    )
    assert (
        audit_event_to_run_event_type('tool_call_completed')
        == RunEventType.TOOL_CALL_COMPLETED
    )
    assert (
        audit_event_to_run_event_type('tool_call_failed')
        == RunEventType.TOOL_CALL_FAILED
    )
    assert audit_event_to_run_event_type('run_completed') == RunEventType.RUN_COMPLETED
    assert audit_event_to_run_event_type('run_failed') == RunEventType.RUN_FAILED


def test_audit_event_to_run_event_type_legacy_events_return_none() -> None:
    """Still-unmapped audit event types return None, not raise."""
    # Genuinely unmapped (planned for later phases, no taxonomy entry yet).
    assert audit_event_to_run_event_type('plan_resolved') is None
    assert audit_event_to_run_event_type('context_compacted') is None
    assert audit_event_to_run_event_type('session_start') is None
    assert audit_event_to_run_event_type('unknown_event_type') is None


def test_audit_event_to_run_event_type_evidence_events_now_mapped() -> None:
    """M2-T002 (§16): evidence events the bundle reads are now typed/surfaced."""
    assert audit_event_to_run_event_type('tool_call_started') == (
        RunEventType.TOOL_CALL_STARTED
    )
    assert audit_event_to_run_event_type('model_route') == RunEventType.MODEL_ROUTE
    assert audit_event_to_run_event_type('git_sandbox_started') == (
        RunEventType.GIT_SANDBOX_STARTED
    )
    assert audit_event_to_run_event_type('approval_granted') == (
        RunEventType.APPROVAL_GRANTED
    )
    assert audit_event_to_run_event_type('undo_applied') == RunEventType.UNDO_APPLIED


def test_read_run_events_from_audit_mapped_events_only() -> None:
    """Test that read_run_events_from_audit filters to only mapped event types."""
    # Handcrafted list of audit entries: mix of M0 and legacy events
    entries: list[dict[str, Any]] = [
        {
            'event_id': 'ev-1',
            'event_type': 'run_started',
            'run_id': 'run-test',
            'payload': {'task': 'test task'},
            'created_at': '2026-06-13T10:00:00+00:00',
        },
        {
            'event_id': 'ev-2',
            'event_type': 'tool_call_started',  # Legacy: not in M0
            'run_id': 'run-test',
            'payload': {'tool_name': 'test_tool', 'call_id': 'call-1'},
            'created_at': '2026-06-13T10:00:01+00:00',
        },
        {
            'event_id': 'ev-3',
            'event_type': 'tool_call_requested',  # M0 event
            'run_id': 'run-test',
            'payload': {'tool_name': 'test_tool', 'call_id': 'call-1'},
            'created_at': '2026-06-13T10:00:02+00:00',
        },
        {
            'event_id': 'ev-4',
            'event_type': 'tool_call_completed',  # M0 event
            'run_id': 'run-test',
            'payload': {'tool_name': 'test_tool', 'result': 'ok'},
            'created_at': '2026-06-13T10:00:03+00:00',
        },
        {
            'event_id': 'ev-5',
            'event_type': 'model_route',  # evidence event — now mapped (§16)
            'run_id': 'run-test',
            'payload': {'resolved_model': 'claude-opus'},
            'created_at': '2026-06-13T10:00:04+00:00',
        },
        {
            'event_id': 'ev-5b',
            'event_type': 'plan_resolved',  # still unmapped legacy → skipped
            'run_id': 'run-test',
            'payload': {'plan': 'x'},
            'created_at': '2026-06-13T10:00:04.5+00:00',
        },
        {
            'event_id': 'ev-6',
            'event_type': 'run_completed',  # M0 event
            'run_id': 'run-test',
            'payload': {'status': 'completed'},
            'created_at': '2026-06-13T10:00:05+00:00',
        },
    ]

    events = read_run_events_from_audit(entries)

    # All taxonomy events surface (M0 + M2 evidence: tool_call_started and
    # model_route now mapped per §16). Only still-unmapped plan_resolved skips.
    assert [e.type for e in events] == [
        RunEventType.RUN_STARTED,
        RunEventType.TOOL_CALL_STARTED,
        RunEventType.TOOL_CALL_REQUESTED,
        RunEventType.TOOL_CALL_COMPLETED,
        RunEventType.MODEL_ROUTE,
        RunEventType.RUN_COMPLETED,
    ]

    # Monotonic seq over surfaced events only, 1..N.
    assert [e.seq for e in events] == [1, 2, 3, 4, 5, 6]

    # run_id and payload preserved.
    assert all(e.run_id == 'run-test' for e in events)
    assert events[0].payload.get('task') == 'test task'


def test_read_run_events_from_audit_preserves_redaction() -> None:
    """Test that redaction markers in payloads are preserved unchanged."""
    entries: list[dict[str, Any]] = [
        {
            'event_id': 'ev-1',
            'event_type': 'run_started',
            'run_id': 'run-redacted',
            'payload': {'command': '[redacted]', 'task': 'some task'},
            'created_at': '2026-06-13T10:00:00+00:00',
        },
        {
            'event_id': 'ev-2',
            'event_type': 'tool_call_completed',
            'run_id': 'run-redacted',
            'payload': {
                'tool_name': 'bash',
                'result': '[redacted]',
                'exit_code': 0,
            },
            'created_at': '2026-06-13T10:00:01+00:00',
        },
    ]

    events = read_run_events_from_audit(entries)

    assert len(events) == 2

    # Check that redaction markers are preserved
    assert events[0].payload['command'] == '[redacted]'
    assert events[1].payload['result'] == '[redacted]'

    # Other fields should be present and unchanged
    assert events[0].payload['task'] == 'some task'
    assert events[1].payload['exit_code'] == 0


def test_read_run_events_from_jsonl_file(tmp_path: Path) -> None:
    """Test that read_run_events_from_jsonl reads and parses a JSONL file correctly."""
    # Write a test JSONL file with mixed M0/legacy events and blank lines
    jsonl_file = tmp_path / 'test_audit.jsonl'

    entries = [
        {
            'event_id': 'ev-1',
            'event_type': 'run_started',
            'run_id': 'run-jsonl-test',
            'payload': {'task': 'test'},
            'created_at': '2026-06-13T10:00:00+00:00',
        },
        {
            'event_id': 'ev-2',
            'event_type': 'plan_resolved',  # still-unmapped legacy → skipped
            'run_id': 'run-jsonl-test',
            'payload': {'plan': 'x'},
            'created_at': '2026-06-13T10:00:01+00:00',
        },
        {
            'event_id': 'ev-3',
            'event_type': 'tool_call_requested',
            'run_id': 'run-jsonl-test',
            'payload': {'tool_name': 'test_tool', 'call_id': 'call-1'},
            'created_at': '2026-06-13T10:00:02+00:00',
        },
        {
            'event_id': 'ev-4',
            'event_type': 'run_completed',
            'run_id': 'run-jsonl-test',
            'payload': {'status': 'completed'},
            'created_at': '2026-06-13T10:00:03+00:00',
        },
    ]

    # Write with blank lines interspersed
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(entries[0], sort_keys=True) + '\n')
        f.write('\n')  # Blank line (should be tolerated)
        f.write(json.dumps(entries[1], sort_keys=True) + '\n')
        f.write(json.dumps(entries[2], sort_keys=True) + '\n')
        f.write('  \n')  # Whitespace-only line (should be tolerated)
        f.write(json.dumps(entries[3], sort_keys=True) + '\n')

    events = read_run_events_from_jsonl(jsonl_file)

    # Should read 3 events (run_started, tool_call_requested, run_completed);
    # the still-unmapped plan_resolved is skipped.
    assert len(events) == 3

    assert events[0].type == RunEventType.RUN_STARTED
    assert events[0].run_id == 'run-jsonl-test'

    assert events[1].type == RunEventType.TOOL_CALL_REQUESTED
    assert events[1].seq == 2  # Monotonic, skipping legacy event

    assert events[2].type == RunEventType.RUN_COMPLETED
    assert events[2].seq == 3


def test_read_run_events_from_jsonl_file_not_found() -> None:
    """Test that read_run_events_from_jsonl raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        read_run_events_from_jsonl('/nonexistent/path/audit.jsonl')


def test_read_run_events_from_jsonl_invalid_json(tmp_path: Path) -> None:
    """Test that read_run_events_from_jsonl raises on invalid JSON."""
    bad_jsonl_file = tmp_path / 'bad_audit.jsonl'

    with open(bad_jsonl_file, 'w', encoding='utf-8') as f:
        f.write('{"event_type": "run_started", "run_id": "run-1"}\n')
        f.write('not valid json at all\n')  # Invalid JSON

    with pytest.raises(json.JSONDecodeError):
        read_run_events_from_jsonl(bad_jsonl_file)


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


def test_end_to_end_real_run_to_jsonl_to_events(tmp_path: Path) -> None:
    """End-to-end: drive a real run, write JSONL, read it back as typed events.

    This verifies that:
    1. AgentRunner emits M0 events to the spine
    2. AuditLogger consumer records them to JSONL
    3. read_run_events_from_jsonl can read the JSONL back
    4. The event sequence includes RUN_STARTED and RUN_COMPLETED
    5. Legacy events (tool_call_started if any) are correctly skipped
    """
    audit_path = tmp_path / 'run_audit.jsonl'
    audit = AuditLogger(path=audit_path)
    spine = EventSpine()

    runner = AgentRunner(
        registry=build_test_registry(),
        audit=audit,
        event_spine=spine,
    )

    def decide(context: dict[str, Any]):
        """Simple decision: one tool call then final answer."""
        if not context['observations']:
            return ToolRequest(
                tool_name='test_echo',
                arguments={'value': 'hello'},
                call_id='call-1',
            )
        return FinalAnswer(
            content=f'Done: {context["observations"][0]["result"]["value"]}'
        )

    # Run the agent
    result = runner.run(task='e2e test', decide=decide, run_id='run-e2e')

    assert result.status == 'completed'
    assert result.tool_calls == 1

    # Now read the JSONL back as RunEvents
    events = read_run_events_from_jsonl(audit_path)

    # Should have at least RUN_STARTED and RUN_COMPLETED
    assert len(events) >= 2

    # First event should be RUN_STARTED
    assert events[0].type == RunEventType.RUN_STARTED
    assert events[0].run_id == 'run-e2e'

    # Last event should be RUN_COMPLETED
    assert events[-1].type == RunEventType.RUN_COMPLETED
    assert events[-1].run_id == 'run-e2e'

    # All events should have run_id matching
    assert all(e.run_id == 'run-e2e' for e in events)

    # All events should have monotonic sequence
    for i, event in enumerate(events, start=1):
        assert event.seq == i

    # Verify that tool-related events are present
    event_types = [e.type for e in events]
    # At minimum, we should have a TOOL_CALL_COMPLETED event
    assert RunEventType.TOOL_CALL_COMPLETED in event_types

    # Verify ordering: RUN_STARTED before any tool events before RUN_COMPLETED
    run_started_idx = event_types.index(RunEventType.RUN_STARTED)
    tool_completed_idx = event_types.index(RunEventType.TOOL_CALL_COMPLETED)
    run_completed_idx = event_types.index(RunEventType.RUN_COMPLETED)

    assert run_started_idx < tool_completed_idx < run_completed_idx
