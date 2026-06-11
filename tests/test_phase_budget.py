from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from teaagent.budget import Phase, PhaseBudget
from teaagent.phase_tracker import PhaseTracker
from teaagent.types import RunBudget


def _make_phase_budget_runner(
    phase_budgets: dict[Phase, PhaseBudget],
    max_iterations: int = 25,
    max_tool_calls: int = 25,
):
    from teaagent.phase_tracker import PhaseTracker
    from teaagent.runner import AgentRunner
    from teaagent.types import AuditLogger, RunBudget, ToolAnnotations, ToolRegistry

    registry = ToolRegistry()
    registry.register(
        name='echo',
        description='echo',
        input_schema={
            'type': 'object',
            'properties': {'msg': {'type': 'string'}},
            'required': ['msg'],
        },
        output_schema={
            'type': 'object',
            'properties': {'out': {'type': 'string'}},
            'required': ['out'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {'out': args['msg']},
    )
    budget = RunBudget(
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
        phase_budgets=phase_budgets,
    )
    tracker = PhaseTracker(Phase.PLAN)
    tracker.set_cost_start(0.0)
    return AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        budget=budget,
        phase_tracker=tracker,
    )


def test_phase_values() -> None:
    assert Phase.PLAN.value == 'plan'
    assert Phase.EXECUTE.value == 'execute'
    assert Phase.REVIEW.value == 'review'
    assert Phase.SYNTHESIS.value == 'synthesis'


def test_phase_is_str_enum() -> None:
    assert isinstance(Phase.PLAN, str)


def test_creates_with_required_fields() -> None:
    pb = PhaseBudget(phase=Phase.PLAN, max_iterations=5, max_tool_calls=3)
    assert pb.phase == Phase.PLAN
    assert pb.max_iterations == 5
    assert pb.max_tool_calls == 3
    assert pb.max_estimated_cost_cents is None


def test_creates_with_cost_cap() -> None:
    pb = PhaseBudget(
        phase=Phase.EXECUTE,
        max_iterations=10,
        max_tool_calls=5,
        max_estimated_cost_cents=200,
    )
    assert pb.max_estimated_cost_cents == 200


def test_is_frozen() -> None:
    pb = PhaseBudget(phase=Phase.PLAN, max_iterations=5, max_tool_calls=3)
    with pytest.raises(FrozenInstanceError):
        pb.max_iterations = 10


def test_phase_budget_for_returns_specific_when_configured() -> None:
    plan_budget = PhaseBudget(phase=Phase.PLAN, max_iterations=3, max_tool_calls=2)
    budget = RunBudget(
        max_iterations=25,
        max_tool_calls=25,
        phase_budgets={Phase.PLAN: plan_budget},
    )
    resolved = budget.phase_budget_for(Phase.PLAN)
    assert resolved.max_iterations == 3
    assert resolved.max_tool_calls == 2
    assert resolved.max_estimated_cost_cents is None


def test_phase_budget_for_falls_back_to_overall_defaults() -> None:
    budget = RunBudget(
        max_iterations=25, max_tool_calls=25, max_estimated_cost_cents=500
    )
    resolved = budget.phase_budget_for(Phase.EXECUTE)
    assert resolved.phase == Phase.EXECUTE
    assert resolved.max_iterations == 25
    assert resolved.max_tool_calls == 25
    assert resolved.max_estimated_cost_cents == 500


def test_phase_budget_for_returns_specific_cost_when_set() -> None:
    review_budget = PhaseBudget(
        phase=Phase.REVIEW,
        max_iterations=5,
        max_tool_calls=5,
        max_estimated_cost_cents=100,
    )
    budget = RunBudget(
        max_estimated_cost_cents=500,
        phase_budgets={Phase.REVIEW: review_budget},
    )
    resolved = budget.phase_budget_for(Phase.REVIEW)
    assert resolved.max_estimated_cost_cents == 100


def test_phase_budget_for_falls_back_cost_to_none_when_overall_none() -> None:
    budget = RunBudget(max_estimated_cost_cents=None)
    resolved = budget.phase_budget_for(Phase.SYNTHESIS)
    assert resolved.max_estimated_cost_cents is None


def test_multiple_phase_budgets_coexist() -> None:
    plan_budget = PhaseBudget(phase=Phase.PLAN, max_iterations=3, max_tool_calls=2)
    exec_budget = PhaseBudget(phase=Phase.EXECUTE, max_iterations=10, max_tool_calls=8)
    budget = RunBudget(
        phase_budgets={Phase.PLAN: plan_budget, Phase.EXECUTE: exec_budget},
    )
    assert budget.phase_budget_for(Phase.PLAN).max_iterations == 3
    assert budget.phase_budget_for(Phase.EXECUTE).max_iterations == 10
    assert budget.phase_budget_for(Phase.REVIEW).max_iterations == 25


def test_valid_phase_budgets_pass_validation() -> None:
    budget = RunBudget(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=3, max_tool_calls=2
            ),
        },
    )
    budget.validate()


def test_phase_budget_max_iterations_less_than_one_raises() -> None:
    budget = RunBudget(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=0, max_tool_calls=2
            ),
        },
    )
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_iterations' in str(ctx.value)
    assert 'plan' in str(ctx.value)


def test_phase_budget_negative_tool_calls_raises() -> None:
    budget = RunBudget(
        phase_budgets={
            Phase.EXECUTE: PhaseBudget(
                phase=Phase.EXECUTE, max_iterations=1, max_tool_calls=-1
            ),
        },
    )
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_tool_calls' in str(ctx.value)


def test_phase_budget_negative_cost_raises() -> None:
    budget = RunBudget(
        phase_budgets={
            Phase.REVIEW: PhaseBudget(
                phase=Phase.REVIEW,
                max_iterations=1,
                max_tool_calls=1,
                max_estimated_cost_cents=-1,
            ),
        },
    )
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_estimated_cost_cents' in str(ctx.value)


def test_runtime_budget_is_frozen() -> None:
    budget = RunBudget()
    with pytest.raises(FrozenInstanceError):
        budget.max_iterations = 99


def test_phase_iterations_start_at_zero() -> None:
    tracker = PhaseTracker()
    assert tracker.phase_iterations() == 0


def test_record_iteration_increments_counter() -> None:
    tracker = PhaseTracker()
    tracker.record_iteration()
    assert tracker.phase_iterations() == 1
    tracker.record_iteration()
    tracker.record_iteration()
    assert tracker.phase_iterations() == 3


def test_phase_tool_calls_start_at_zero() -> None:
    tracker = PhaseTracker()
    assert tracker.phase_tool_calls() == 0


def test_record_tool_call_increments_counter() -> None:
    tracker = PhaseTracker()
    tracker.record_tool_call()
    assert tracker.phase_tool_calls() == 1
    tracker.record_tool_call()
    assert tracker.phase_tool_calls() == 2


def test_default_phase_is_plan() -> None:
    tracker = PhaseTracker()
    assert tracker.current_phase == Phase.PLAN


def test_phase_cost_cents_returns_zero_initially() -> None:
    tracker = PhaseTracker()
    assert tracker.phase_cost_cents(50.0) == 50.0
    tracker.set_cost_start(0.0)
    assert tracker.phase_cost_cents(50.0) == 50.0


def test_phase_cost_cents_delta_from_start() -> None:
    tracker = PhaseTracker()
    tracker.set_cost_start(100.0)
    assert tracker.phase_cost_cents(150.0) == 50.0
    assert tracker.phase_cost_cents(200.0) == 100.0


def test_phase_cost_cents_never_negative() -> None:
    tracker = PhaseTracker()
    tracker.set_cost_start(200.0)
    assert tracker.phase_cost_cents(100.0) == 0.0


def test_transition_resets_counters() -> None:
    tracker = PhaseTracker()
    tracker.record_iteration()
    tracker.record_iteration()
    tracker.record_tool_call()
    assert tracker.phase_iterations() == 2
    assert tracker.phase_tool_calls() == 1

    tracker.transition(Phase.EXECUTE)
    assert tracker.current_phase == Phase.EXECUTE
    assert tracker.phase_iterations() == 0
    assert tracker.phase_tool_calls() == 0


def test_transition_preserves_cost_start() -> None:
    tracker = PhaseTracker()
    tracker.set_cost_start(0.0)
    tracker.transition(Phase.EXECUTE, total_cost_cents=150.0)
    assert tracker.phase_cost_cents(200.0) == 50.0


def test_transition_does_not_affect_other_phases() -> None:
    tracker = PhaseTracker()
    tracker.record_iteration()
    tracker.record_iteration()
    assert tracker.phase_iterations() == 2

    tracker.transition(Phase.EXECUTE)
    assert tracker.phase_iterations() == 0

    tracker.transition(Phase.PLAN)
    assert tracker.phase_iterations() == 0


def test_phase_iteration_budget_enforced() -> None:
    from teaagent.runner import FinalAnswer, ToolRequest

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=2, max_tool_calls=10
            ),
        },
        max_iterations=10,
    )

    call_count = {'n': 0}

    def decide_two_then_done(ctx):
        call_count['n'] += 1
        if call_count['n'] < 2:
            return ToolRequest(
                tool_name='echo', arguments={'msg': f't{call_count["n"]}'}
            )
        return FinalAnswer(content='done')

    result = runner.run(
        task='test',
        decide=decide_two_then_done,
        run_id='run-phase-iter',
    )
    assert result.status == 'completed'
    assert result.iterations == 2

    runner2 = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=1, max_tool_calls=10
            ),
        },
        max_iterations=10,
    )

    result2 = runner2.run(
        task='test',
        decide=lambda ctx: FinalAnswer(content='done'),
        run_id='run-phase-iter2',
    )
    assert result2.status == 'completed'
    assert result2.iterations == 1


def test_phase_iteration_budget_exceeds_before_overall() -> None:
    from teaagent.runner import ToolRequest

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=2, max_tool_calls=10
            ),
        },
        max_iterations=10,
    )

    counter = {'n': 0}

    def decide_never_finish(ctx):
        counter['n'] += 1
        return ToolRequest(tool_name='echo', arguments={'msg': f'hi{counter["n"]}'})

    result = runner.run(
        task='test', decide=decide_never_finish, run_id='run-phase-iter3'
    )
    assert 'failed' in result.status
    assert 'iteration budget exceeded' in (result.error_message or '')


def test_phase_tool_call_budget_enforced() -> None:
    from teaagent.runner import ToolRequest

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=10, max_tool_calls=0
            ),
        },
        max_iterations=10,
        max_tool_calls=10,
    )

    result = runner.run(
        task='test',
        decide=lambda ctx: ToolRequest(tool_name='echo', arguments={'msg': 'hi'}),
        run_id='run-phase-tools',
    )
    assert 'failed' in result.status
    assert 'tool-call budget exceeded' in (result.error_message or '')


def test_phase_cost_budget_enforced() -> None:
    from teaagent.runner import FinalAnswer

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN,
                max_iterations=10,
                max_tool_calls=10,
                max_estimated_cost_cents=50,
            ),
        },
        max_iterations=10,
    )

    def decide_with_cost(ctx):
        ctx['_cost_cents'] = ctx.get('_cost_cents', 0.0) + 200.0
        return FinalAnswer(content='done')

    result = runner.run(
        task='test',
        decide=decide_with_cost,
        run_id='run-phase-cost',
    )
    assert 'failed' in result.status
    assert 'cost budget exceeded' in (result.error_message or '')


def test_phase_budget_warning_audit_event_emitted() -> None:
    from teaagent.runner import ToolRequest

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=1, max_tool_calls=10
            ),
        },
        max_iterations=10,
    )

    counter = {'n': 0}

    def decide_never_finish(ctx):
        counter['n'] += 1
        return ToolRequest(tool_name='echo', arguments={'msg': f'hi{counter["n"]}'})

    runner.run(task='test', decide=decide_never_finish, run_id='run-phase-audit')

    warning_events = [
        e for e in runner.audit.events if e.event_type == 'phase_budget_warning'
    ]
    assert len(warning_events) == 1
    event = warning_events[0]
    assert event.payload['phase'] == 'plan'
    assert event.payload['metric'] == 'iterations'
    assert event.payload['limit'] == 1
    assert event.payload['current'] > 1


def test_no_phase_budget_causes_no_phase_enforcement() -> None:
    from teaagent.runner import FinalAnswer

    runner = _make_phase_budget_runner(
        phase_budgets={}, max_iterations=10, max_tool_calls=10
    )

    result = runner.run(
        task='test',
        decide=lambda ctx: FinalAnswer(content='done'),
        run_id='run-no-phase',
    )
    assert result.status == 'completed'
    assert result.iterations > 0


def test_different_phase_has_different_budget() -> None:
    from teaagent.runner import FinalAnswer, ToolRequest

    runner = _make_phase_budget_runner(
        phase_budgets={
            Phase.PLAN: PhaseBudget(
                phase=Phase.PLAN, max_iterations=2, max_tool_calls=10
            ),
            Phase.EXECUTE: PhaseBudget(
                phase=Phase.EXECUTE, max_iterations=10, max_tool_calls=10
            ),
        },
        max_iterations=10,
    )

    def decide_with_transition(ctx):
        if runner.phase_tracker.current_phase == Phase.PLAN:
            runner.phase_tracker.transition(Phase.EXECUTE, total_cost_cents=0.0)
            return ToolRequest(tool_name='echo', arguments={'msg': 'transitioning'})
        return FinalAnswer(content='done')

    result = runner.run(
        task='test',
        decide=decide_with_transition,
        run_id='run-phase-diff',
    )
    assert result.status == 'completed'
    assert result.iterations > 1
