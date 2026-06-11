from __future__ import annotations

import tempfile

from teaagent import (
    AgentRunner,
    ApprovalPolicy,
    AuditLogger,
    FinalAnswer,
    RunBudget,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
)
from teaagent.ergonomics.approval_store import ApprovalPresetStore

INPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}

OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}


def build_registry(*, destructive: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='pilot_echo',
        description='Return the supplied value for pilot validation.',
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only=not destructive,
            destructive=destructive,
            idempotent=True,
        ),
        handler=lambda args: {'value': args['value']},
    )
    return registry


def test_runner_executes_registered_tool_and_audits_result() -> None:
    audit = AuditLogger()
    runner = AgentRunner(registry=build_registry(), audit=audit)

    def decide(context):
        if not context['observations']:
            return ToolRequest(tool_name='pilot_echo', arguments={'value': 'ok'})
        return FinalAnswer(content=context['observations'][0]['result']['value'])

    result = runner.run(task='echo ok', decide=decide, run_id='run-1')

    assert result.status == 'completed'
    assert result.final_answer.content == 'ok'
    assert 'tool_call_completed' in [event.event_type for event in audit.events]


def test_destructive_tool_requires_exact_call_approval() -> None:
    audit = AuditLogger()
    runner = AgentRunner(registry=build_registry(destructive=True), audit=audit)

    def decide(_context):
        return ToolRequest(
            tool_name='pilot_echo',
            arguments={'value': 'delete'},
            call_id='call-1',
        )

    result = runner.run(task='destructive action', decide=decide, run_id='run-2')

    assert result.status == 'pending_approval'
    assert result.metadata['approval']['call_id'] == 'call-1'
    assert result.metadata['approval']['arguments']['value'] == 'delete'
    pending = [
        event
        for event in audit.events
        if event.event_type == 'tool_call_pending_approval'
    ]
    assert len(pending) == 1
    assert pending[0].payload['tool_name'] == 'pilot_echo'
    assert pending[0].payload['annotations']['destructive'] is True
    assert 'explicit approval' in pending[0].payload['reason']
    assert audit.events[-1].event_type == 'run_paused'


def test_destructive_tool_can_be_approved_by_hitl_handler() -> None:
    audit = AuditLogger()
    approvals = []
    runner = AgentRunner(
        registry=build_registry(destructive=True),
        audit=audit,
        approval_handler=lambda request: approvals.append(request.call_id) or True,
    )

    def decide(context):
        if not context['observations']:
            return ToolRequest(
                tool_name='pilot_echo',
                arguments={'value': 'approved'},
                call_id='call-hitl',
            )
        return FinalAnswer(content='done')

    result = runner.run(task='destructive action', decide=decide, run_id='run-hitl')

    assert result.status == 'completed'
    assert result.tool_calls == 1
    assert approvals == ['call-hitl']
    assert 'tool_call_approved' in [event.event_type for event in audit.events]


def test_denied_hitl_approval_fails_without_tool_execution() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(destructive=True),
        audit=audit,
        approval_handler=lambda _request: False,
    )

    def decide(_context):
        return ToolRequest(
            tool_name='pilot_echo',
            arguments={'value': 'denied'},
            call_id='call-deny',
        )

    result = runner.run(task='destructive action', decide=decide, run_id='run-deny')

    # After approval gate fix, denied approvals return pending_approval instead of failed:permission
    assert result.status == 'pending_approval'
    assert result.tool_calls == 0
    assert 'tool_call_denied' in [event.event_type for event in audit.events]


def test_approved_destructive_tool_can_run() -> None:
    def decide(context):
        if not context['observations']:
            return ToolRequest(
                tool_name='pilot_echo',
                arguments={'value': 'approved'},
                call_id='call-1',
            )
        return FinalAnswer(content='done')

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store.add_scoped_approval(
            run_id='run-3',
            call_id='call-1',
            tool_name='pilot_echo',
            arguments={'value': 'approved'},
        )
        audit = AuditLogger()
        runner = AgentRunner(
            registry=build_registry(destructive=True),
            audit=audit,
            approval_policy=ApprovalPolicy(
                approval_store=store,
                approval_origin_run_id='run-3',
            ),
        )

        result = runner.run(task='approved action', decide=decide, run_id='run-3')

        assert result.status == 'completed'
        assert result.tool_calls == 1


def test_iteration_budget_stops_non_terminating_agent() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(),
        audit=audit,
        budget=RunBudget(max_iterations=2, max_tool_calls=5),
    )

    def decide(_context):
        return ToolRequest(tool_name='pilot_echo', arguments={'value': 'loop'})

    result = runner.run(task='loop forever', decide=decide, run_id='run-4')

    assert result.status == 'failed:model_logic'
    assert result.iterations == 2


def test_schema_rejects_unexpected_arguments() -> None:
    audit = AuditLogger()
    runner = AgentRunner(registry=build_registry(), audit=audit)

    def decide(_context):
        return ToolRequest(
            tool_name='pilot_echo',
            arguments={'value': 'ok', 'extra': 'blocked'},
        )

    result = runner.run(task='bad schema', decide=decide, run_id='run-5')

    assert result.status == 'failed:model_logic'


def test_cost_budget_blocks_tool_after_decision_cost_update() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=1, max_tool_calls=1, max_estimated_cost_cents=1
        ),
    )

    def decide(context):
        context['_cost_cents'] = 2.0
        return ToolRequest(tool_name='pilot_echo', arguments={'value': 'over'})

    result = runner.run(task='cost overflow', decide=decide, run_id='run-cost-tool')

    assert result.status == 'failed:model_logic'
    assert result.tool_calls == 0
    assert 'tool_call_started' not in [event.event_type for event in audit.events]
    assert audit.events[-1].payload['cost_cents'] == 2.0


def test_initial_observations_replayed_into_context() -> None:
    audit = AuditLogger()
    runner = AgentRunner(registry=build_registry(), audit=audit)
    seen: list[list[dict]] = []

    def decide(context):
        seen.append(list(context['observations']))
        return FinalAnswer(content='ok')

    replayed = [
        {
            'call_id': 'r1',
            'tool_name': 'pilot_echo',
            'result': {'value': 'earlier'},
        },
        {'call_id': 'r2', 'tool_name': 'pilot_echo', 'result': {'value': 'later'}},
    ]
    result = runner.run(
        task='resume',
        decide=decide,
        run_id='run-replay',
        initial_observations=replayed,
    )

    assert result.status == 'completed'
    assert result.tool_calls == 2
    assert seen[0] == replayed
    run_started = next(e for e in audit.events if e.event_type == 'run_started')
    assert run_started.payload['replayed_observations'] == 2


def test_initial_observations_count_against_tool_call_budget() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(),
        audit=audit,
        budget=RunBudget(max_iterations=3, max_tool_calls=2),
    )

    def decide(_context):
        return ToolRequest(tool_name='pilot_echo', arguments={'value': 'next'})

    replayed = [
        {'call_id': 'r1', 'tool_name': 'pilot_echo', 'result': {'value': 'a'}},
        {'call_id': 'r2', 'tool_name': 'pilot_echo', 'result': {'value': 'b'}},
    ]
    result = runner.run(
        task='budget-replay',
        decide=decide,
        run_id='run-budget-replay',
        initial_observations=replayed,
    )

    assert result.status == 'failed:model_logic'
    assert result.tool_calls == 2


def test_cost_budget_blocks_final_after_decision_cost_update() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=build_registry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=1, max_tool_calls=1, max_estimated_cost_cents=1
        ),
    )

    def decide(context):
        context['_cost_cents'] = 2.0
        return FinalAnswer(content='too expensive')

    result = runner.run(
        task='cost overflow final', decide=decide, run_id='run-cost-final'
    )

    assert result.status == 'failed:model_logic'
    assert result.final_answer is None
    assert 'run_completed' not in [event.event_type for event in audit.events]
