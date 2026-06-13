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
    audit_event_to_run_event_type,
)
from teaagent.errors import ToolPermissionError
from teaagent.runner._events import (
    _AUDIT_EVENT_TO_RUN_EVENT_TYPE,
    _RUN_EVENT_TO_AUDIT_EVENT_TYPE,
    run_event_to_audit_event_type,
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
#
# M3 Slice B added tool_call_requested (the plan-gate interceptor emit) —
# the contract was extended to include this event. The six original entries
# (run_started, iteration_started, tool_call_started, tool_call_completed,
# iteration_started, run_completed) retain their shape.
_GOLDEN_COMPLETED_CONTRACT: list[tuple[str, tuple[str, ...]]] = [
    ('run_started', ('replayed_observations', 'task')),
    ('iteration_started', ('iteration',)),
    (
        'tool_call_requested',
        ('arguments', 'tool_name'),
    ),
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


def test_all_run_event_types_round_trip_through_mappers() -> None:
    """Every RunEventType member round-trips through both mapper directions.

    Covers all 26 members (7 M0 + 19 M2 evidence-event taxonomy) — forward
    through run_event_to_audit_event_type then back through
    audit_event_to_run_event_type, and inverse through the dict mappers.
    """
    for event_type in RunEventType:
        aud_type = run_event_to_audit_event_type(event_type)
        back = audit_event_to_run_event_type(aud_type)
        assert back == event_type

    for aud_type, run_type in _AUDIT_EVENT_TO_RUN_EVENT_TYPE.items():
        assert _RUN_EVENT_TO_AUDIT_EVENT_TYPE[run_type] == aud_type

    assert len(_RUN_EVENT_TO_AUDIT_EVENT_TYPE) == len(RunEventType)
    assert len(_AUDIT_EVENT_TO_RUN_EVENT_TYPE) == len(RunEventType)


# ---------------------------------------------------------------------------
# M3-T001: PlanGateInterceptor unit tests
# ---------------------------------------------------------------------------


def _make_tcr_event(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    plan_contract: Any = None,
    *,
    annotations: dict[str, bool] | None = None,
    call_id: str = '',
    description: str = '',
) -> RunEvent:
    """Build a TOOL_CALL_REQUESTED RunEvent for testing."""
    payload: dict[str, Any] = {'tool_name': tool_name}
    if arguments is not None:
        payload['arguments'] = arguments
    if plan_contract is not None:
        payload['plan_contract'] = plan_contract
    # M4-T001: approval fields.
    payload['annotations'] = annotations or {}
    payload['call_id'] = call_id
    payload['description'] = description
    return RunEvent(
        type=RunEventType.TOOL_CALL_REQUESTED,
        run_id='test-plan-gate',
        payload=payload,
        seq=1,
    )


def _make_plan_validator(
    permission_mode: str = 'prompt',
    require_plan: bool = False,
    skip_plan_check: bool = False,
) -> Any:
    """Build a PlanValidator with minimal configuration."""
    from teaagent.approval_manager import PermissionMode
    from teaagent.policy import ApprovalPolicy

    policy = ApprovalPolicy(permission_mode=PermissionMode(permission_mode))
    from teaagent.runner._plan_validator import PlanValidator

    return PlanValidator(
        approval_policy=policy,
        require_plan=require_plan,
        skip_plan_check=skip_plan_check,
    )


def test_plan_gate_interceptor_ignores_non_tool_events() -> None:
    """PlanGateInterceptor is a no-op for non-TOOL_CALL_REQUESTED events."""
    from teaagent.runner._plan_validator import PlanGateInterceptor

    interceptor = PlanGateInterceptor(_make_plan_validator())
    event = RunEvent(
        type=RunEventType.RUN_STARTED,
        run_id='test',
        payload={},
        seq=1,
    )
    # Should not raise.
    interceptor(event)
    assert interceptor.last_decision is None


def test_plan_gate_interceptor_allows_write_tool_without_plan_check() -> None:
    """Write tool passes when plan check is not required."""
    from teaagent.runner._plan_validator import PlanGateInterceptor

    interceptor = PlanGateInterceptor(_make_plan_validator())
    event = _make_tcr_event('workspace_write_file', arguments={'path': 'test.txt'})
    interceptor(event)
    assert interceptor.last_decision is None


def test_plan_gate_interceptor_blocks_write_when_plan_required() -> None:
    """Write tool with require_plan=True but no plan contract is blocked."""
    from teaagent.approval_manager import PermissionMode
    from teaagent.policy import ApprovalPolicy
    from teaagent.runner._plan_validator import PlanGateInterceptor, PlanValidator

    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    pv = PlanValidator(approval_policy=policy, require_plan=True)
    interceptor = PlanGateInterceptor(pv)

    # No plan_contract in payload → should be blocked.
    event = _make_tcr_event('workspace_write_file', arguments={'path': 'test.txt'})
    with pytest.raises(ToolPermissionError) as exc_info:
        interceptor(event)
    assert 'plan' in str(exc_info.value).lower()
    assert interceptor.last_decision is not None


def test_plan_gate_interceptor_shadow_mode_does_not_raise() -> None:
    """Shadow mode (raise_on_deny=False) records decision without raising."""
    from teaagent.approval_manager import PermissionMode
    from teaagent.policy import ApprovalPolicy
    from teaagent.runner._plan_validator import PlanGateInterceptor, PlanValidator

    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    pv = PlanValidator(approval_policy=policy, require_plan=True)
    interceptor = PlanGateInterceptor(pv, raise_on_deny=False)

    event = _make_tcr_event('workspace_write_file', arguments={'path': 'test.txt'})
    # Should NOT raise in shadow mode.
    interceptor(event)
    assert interceptor.last_decision is not None


def test_plan_gate_interceptor_allows_non_write_tool() -> None:
    """Non-write tools pass regardless of plan state."""
    from teaagent.approval_manager import PermissionMode
    from teaagent.policy import ApprovalPolicy
    from teaagent.runner._plan_validator import PlanGateInterceptor, PlanValidator

    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    pv = PlanValidator(approval_policy=policy, require_plan=True)
    interceptor = PlanGateInterceptor(pv)

    # A read-only tool like glob_search should always pass the gate.
    event = _make_tcr_event('glob_search', arguments={'pattern': '**/*.py'})
    interceptor(event)
    assert interceptor.last_decision is None


# ---------------------------------------------------------------------------
# M3-T002 Slice A: parity test — interceptor decision == inline decision
# ---------------------------------------------------------------------------


def _interceptor_decision(
    interceptor: Any,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    plan_contract: Any = None,  # noqa: ANN401
) -> str | None:
    """Compute the plan gate decision via the interceptor path.

    Returns the error string (blocked) or None (allowed).
    """
    event = _make_tcr_event(tool_name, arguments, plan_contract)
    try:
        interceptor(event)
        return interceptor.last_decision
    except ToolPermissionError as exc:
        return str(exc)


def _inline_decision(
    plan_validator: Any,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    plan_contract: Any = None,  # noqa: ANN401
) -> str | None:
    """Compute the plan gate decision via the inline path (evaluate_write_gate).

    Returns the error string (blocked) or None (allowed).
    """
    context: dict[str, Any] = {}
    if plan_contract is not None:
        context['plan_contract'] = plan_contract
    try:
        return plan_validator.evaluate_write_gate(
            tool_name=tool_name,
            context=context,
            tool_arguments=arguments,
        )
    except ToolPermissionError as exc:
        return str(exc)


_PLAN_PARITY_SCENARIOS = [
    # (name, permission_mode, require_plan, tool_name, arguments, plan_contract, expect_denied)
    (
        'write_in_prompt_mode',
        'prompt',
        False,
        'workspace_write_file',
        {'path': 'x.txt'},
        None,
        False,
    ),
    (
        'write_in_workspace_write_no_plan',
        'workspace-write',
        True,
        'workspace_write_file',
        {'path': 'x.txt'},
        None,
        True,
    ),
    (
        'write_in_workspace_write_with_plan',
        'workspace-write',
        True,
        'workspace_write_file',
        {'path': 'x.txt'},
        {'content_hash': 'abc'},
        False,
    ),
    (
        'read_only_glob',
        'read-only',
        False,
        'glob_search',
        {'pattern': '**/*.py'},
        None,
        False,
    ),
]


def test_plan_gate_interceptor_parity() -> None:
    """Interceptor decision matches inline decision for every key scenario.

    Drives the allow path and each plan-drift denial reason code,
    asserting the interceptor produces the same error string (or None)
    as the still-authoritative inline ``PlanValidator.evaluate_write_gate()``.
    """
    from teaagent.approval_manager import PermissionMode
    from teaagent.policy import ApprovalPolicy
    from teaagent.runner._plan_validator import PlanGateInterceptor, PlanValidator

    errors: list[str] = []
    for (
        name,
        perm_mode_str,
        require_plan,
        tool_name,
        arguments,
        plan_contract,
        expect_denied,
    ) in _PLAN_PARITY_SCENARIOS:
        policy = ApprovalPolicy(permission_mode=PermissionMode(perm_mode_str))
        pv = PlanValidator(approval_policy=policy, require_plan=require_plan)
        interceptor = PlanGateInterceptor(pv)

        inline_result = _inline_decision(pv, tool_name, arguments, plan_contract)
        interceptor_result = _interceptor_decision(
            interceptor, tool_name, arguments, plan_contract
        )

        if inline_result != interceptor_result:
            errors.append(
                f'{name}: inline={inline_result!r} != interceptor={interceptor_result!r}'
            )
        if expect_denied:
            assert inline_result is not None, (
                f'{name}: expected denial but inline allowed'
            )
            assert interceptor_result is not None, (
                f'{name}: expected denial but interceptor allowed'
            )
        else:
            assert inline_result is None, (
                f'{name}: expected allow but inline denied: {inline_result}'
            )
            assert interceptor_result is None, (
                f'{name}: expected allow but interceptor denied: {interceptor_result}'
            )

    assert not errors, 'Parity mismatches:\n' + '\n'.join(errors)


# ---------------------------------------------------------------------------
# M4 approval gate, Slice A: ApprovalGateInterceptor unit + parity tests
# ---------------------------------------------------------------------------


def test_approval_gate_interceptor_ignores_non_tool_events() -> None:
    """ApprovalGateInterceptor is a no-op for non-TOOL_CALL_REQUESTED events."""
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    interceptor = ApprovalGateInterceptor(policy)

    event = RunEvent(
        type=RunEventType.RUN_STARTED,
        run_id='test',
        payload={},
        seq=1,
    )
    interceptor(event)
    assert interceptor.last_decision is None


def test_approval_gate_interceptor_allows_read_tool() -> None:
    """Read-only tool passes regardless of permission mode."""
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    interceptor = ApprovalGateInterceptor(policy)

    event = _make_tcr_event(
        'glob_search',
        arguments={'pattern': '**/*.py'},
        annotations={'read_only': True, 'destructive': False},
    )
    interceptor(event)
    assert interceptor.last_decision is None


def test_approval_gate_interceptor_blocks_destructive_in_read_only() -> None:
    """Destructive tool in read-only mode is blocked."""
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    interceptor = ApprovalGateInterceptor(policy)

    event = _make_tcr_event(
        'workspace_write_file',
        arguments={'path': 'test.txt'},
        annotations={'read_only': False, 'destructive': True},
    )
    with pytest.raises(ToolPermissionError):
        interceptor(event)
    assert interceptor.last_decision is not None


def test_approval_gate_interceptor_shadow_mode_does_not_raise() -> None:
    """Shadow mode (raise_on_deny=False) records denial without raising."""
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    interceptor = ApprovalGateInterceptor(policy, raise_on_deny=False)

    event = _make_tcr_event(
        'workspace_write_file',
        arguments={'path': 'test.txt'},
        annotations={'read_only': False, 'destructive': True},
    )
    interceptor(event)
    assert interceptor.last_decision is not None


def test_approval_gate_interceptor_allows_destructive_in_allow_mode() -> None:
    """Destructive tool in allow mode passes."""
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    policy = ApprovalPolicy(permission_mode=PermissionMode.ALLOW)
    interceptor = ApprovalGateInterceptor(policy)

    event = _make_tcr_event(
        'workspace_write_file',
        arguments={'path': 'test.txt'},
        annotations={'read_only': False, 'destructive': True},
    )
    interceptor(event)
    assert interceptor.last_decision is None


def _approval_interceptor_decision(
    interceptor: Any,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    plan_contract: Any = None,
    *,
    annotations: dict[str, bool] | None = None,
    call_id: str = '',
    description: str = '',
) -> str | None:
    """Compute the approval gate decision via the interceptor path."""
    event = _make_tcr_event(
        tool_name,
        arguments,
        plan_contract,
        annotations=annotations,
        call_id=call_id,
        description=description,
    )
    try:
        interceptor(event)
        return interceptor.last_decision
    except ToolPermissionError as exc:
        return str(exc)


def _inline_approval_decision(
    approval_policy: Any,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    plan_contract: Any = None,
    *,
    annotations: dict[str, bool] | None = None,
    call_id: str = '',
    description: str = '',
) -> str | None:
    """Compute the approval gate decision via the inline assert_allowed path."""
    ann = annotations or {}
    try:
        approval_policy.assert_allowed(
            tool_name=tool_name,
            call_id=call_id,
            destructive=ann.get('destructive', False),
            arguments=arguments,
            plan_contract=plan_contract,
            read_only=ann.get('read_only', False),
            description=description,
        )
        return None
    except ToolPermissionError as exc:
        return str(exc)


_APPROVAL_PARITY_SCENARIOS = [
    (
        'read_tool_read_only_mode',
        'read-only',
        False,
        'glob_search',
        {'pattern': '**/*.py'},
        None,
        {'read_only': True, 'destructive': False},
        '',
        '',
        False,
    ),
    (
        'destructive_tool_read_only_mode',
        'read-only',
        False,
        'workspace_write_file',
        {'path': 'x.txt'},
        None,
        {'read_only': False, 'destructive': True},
        '',
        '',
        True,
    ),
    (
        'destructive_tool_allow_mode',
        'allow',
        False,
        'workspace_write_file',
        {'path': 'x.txt'},
        None,
        {'read_only': False, 'destructive': True},
        '',
        '',
        False,
    ),
    (
        'destructive_tool_prompt_mode',
        'prompt',
        False,
        'workspace_write_file',
        {'path': 'x.txt'},
        None,
        {'read_only': False, 'destructive': True},
        '',
        '',
        True,
    ),
    (
        'non_destructive_read_workspace_write_mode',
        'workspace-write',
        False,
        'glob_search',
        {'pattern': '**/*.py'},
        None,
        {'read_only': True, 'destructive': False},
        '',
        '',
        False,
    ),
]


def test_approval_gate_interceptor_parity() -> None:
    """Approval gate interceptor decision matches inline assert_allowed.

    Exercises every approval-relevant permission mode, verifying that the
    interceptor (shadow, raise_on_deny=False) agrees with the directly-called
    ApprovalPolicy.assert_allowed().
    """
    from teaagent.policy import ApprovalPolicy, PermissionMode
    from teaagent.runner._approval_manager import ApprovalGateInterceptor

    errors: list[str] = []
    for scenario in _APPROVAL_PARITY_SCENARIOS:
        (
            name,
            perm_mode_str,
            _require_plan,
            tool_name,
            arguments,
            plan_contract,
            annotations,
            call_id,
            description,
            expect_denied,
        ) = scenario

        policy = ApprovalPolicy(permission_mode=PermissionMode(perm_mode_str))
        interceptor = ApprovalGateInterceptor(policy, raise_on_deny=False)

        inline_result = _inline_approval_decision(
            policy,
            tool_name,
            arguments,
            plan_contract,
            annotations=annotations,
            call_id=call_id,
            description=description,
        )
        interceptor_result = _approval_interceptor_decision(
            interceptor,
            tool_name,
            arguments,
            plan_contract,
            annotations=annotations,
            call_id=call_id,
            description=description,
        )

        if inline_result != interceptor_result:
            errors.append(
                f'{name}: inline={inline_result!r} != interceptor={interceptor_result!r}'
            )
        if expect_denied:
            assert inline_result is not None, (
                f'{name}: expected denial but inline allowed'
            )
            assert interceptor_result is not None, (
                f'{name}: expected denial but interceptor allowed'
            )
        else:
            assert inline_result is None, (
                f'{name}: expected allow but inline denied: {inline_result}'
            )
            assert interceptor_result is None, (
                f'{name}: expected allow but interceptor denied: {interceptor_result}'
            )

    assert not errors, 'Parity mismatches:\n' + '\n'.join(errors)
