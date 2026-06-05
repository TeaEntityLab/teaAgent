from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from teaagent.budget import Phase, PhaseBudget, RunBudget
from teaagent.phase_tracker import PhaseTracker


class PhaseEnumTests(unittest.TestCase):
    def test_phase_values(self) -> None:
        self.assertEqual(Phase.PLAN.value, 'plan')
        self.assertEqual(Phase.EXECUTE.value, 'execute')
        self.assertEqual(Phase.REVIEW.value, 'review')
        self.assertEqual(Phase.SYNTHESIS.value, 'synthesis')

    def test_phase_is_str_enum(self) -> None:
        self.assertIsInstance(Phase.PLAN, str)


class PhaseBudgetTests(unittest.TestCase):
    def test_creates_with_required_fields(self) -> None:
        pb = PhaseBudget(phase=Phase.PLAN, max_iterations=5, max_tool_calls=3)
        self.assertEqual(pb.phase, Phase.PLAN)
        self.assertEqual(pb.max_iterations, 5)
        self.assertEqual(pb.max_tool_calls, 3)
        self.assertIsNone(pb.max_estimated_cost_cents)

    def test_creates_with_cost_cap(self) -> None:
        pb = PhaseBudget(
            phase=Phase.EXECUTE,
            max_iterations=10,
            max_tool_calls=5,
            max_estimated_cost_cents=200,
        )
        self.assertEqual(pb.max_estimated_cost_cents, 200)

    def test_is_frozen(self) -> None:
        pb = PhaseBudget(phase=Phase.PLAN, max_iterations=5, max_tool_calls=3)
        with self.assertRaises(FrozenInstanceError):
            pb.max_iterations = 10  # type: ignore[misc]


class RunBudgetPhaseResolutionTests(unittest.TestCase):
    def test_phase_budget_for_returns_specific_when_configured(self) -> None:
        plan_budget = PhaseBudget(phase=Phase.PLAN, max_iterations=3, max_tool_calls=2)
        budget = RunBudget(
            max_iterations=25,
            max_tool_calls=25,
            phase_budgets={Phase.PLAN: plan_budget},
        )
        resolved = budget.phase_budget_for(Phase.PLAN)
        self.assertEqual(resolved.max_iterations, 3)
        self.assertEqual(resolved.max_tool_calls, 2)
        self.assertIsNone(resolved.max_estimated_cost_cents)

    def test_phase_budget_for_falls_back_to_overall_defaults(self) -> None:
        budget = RunBudget(
            max_iterations=25, max_tool_calls=25, max_estimated_cost_cents=500
        )
        resolved = budget.phase_budget_for(Phase.EXECUTE)
        self.assertEqual(resolved.phase, Phase.EXECUTE)
        self.assertEqual(resolved.max_iterations, 25)
        self.assertEqual(resolved.max_tool_calls, 25)
        self.assertEqual(resolved.max_estimated_cost_cents, 500)

    def test_phase_budget_for_returns_specific_cost_when_set(self) -> None:
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
        self.assertEqual(resolved.max_estimated_cost_cents, 100)

    def test_phase_budget_for_falls_back_cost_to_none_when_overall_none(self) -> None:
        budget = RunBudget(max_estimated_cost_cents=None)
        resolved = budget.phase_budget_for(Phase.SYNTHESIS)
        self.assertIsNone(resolved.max_estimated_cost_cents)

    def test_multiple_phase_budgets_coexist(self) -> None:
        plan_budget = PhaseBudget(phase=Phase.PLAN, max_iterations=3, max_tool_calls=2)
        exec_budget = PhaseBudget(
            phase=Phase.EXECUTE, max_iterations=10, max_tool_calls=8
        )
        budget = RunBudget(
            phase_budgets={Phase.PLAN: plan_budget, Phase.EXECUTE: exec_budget},
        )
        self.assertEqual(budget.phase_budget_for(Phase.PLAN).max_iterations, 3)
        self.assertEqual(budget.phase_budget_for(Phase.EXECUTE).max_iterations, 10)
        self.assertEqual(budget.phase_budget_for(Phase.REVIEW).max_iterations, 25)


class RunBudgetValidationTests(unittest.TestCase):
    def test_valid_phase_budgets_pass_validation(self) -> None:
        budget = RunBudget(
            phase_budgets={
                Phase.PLAN: PhaseBudget(
                    phase=Phase.PLAN, max_iterations=3, max_tool_calls=2
                ),
            },
        )
        budget.validate()

    def test_phase_budget_max_iterations_less_than_one_raises(self) -> None:
        budget = RunBudget(
            phase_budgets={
                Phase.PLAN: PhaseBudget(
                    phase=Phase.PLAN, max_iterations=0, max_tool_calls=2
                ),
            },
        )
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_iterations', str(ctx.exception))
        self.assertIn('plan', str(ctx.exception))

    def test_phase_budget_negative_tool_calls_raises(self) -> None:
        budget = RunBudget(
            phase_budgets={
                Phase.EXECUTE: PhaseBudget(
                    phase=Phase.EXECUTE, max_iterations=1, max_tool_calls=-1
                ),
            },
        )
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_tool_calls', str(ctx.exception))

    def test_phase_budget_negative_cost_raises(self) -> None:
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
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_estimated_cost_cents', str(ctx.exception))

    def test_runtime_budget_is_frozen(self) -> None:
        budget = RunBudget()
        with self.assertRaises(FrozenInstanceError):
            budget.max_iterations = 99  # type: ignore[misc]


class PhaseTrackerIterationTests(unittest.TestCase):
    def test_phase_iterations_start_at_zero(self) -> None:
        tracker = PhaseTracker()
        self.assertEqual(tracker.phase_iterations(), 0)

    def test_record_iteration_increments_counter(self) -> None:
        tracker = PhaseTracker()
        tracker.record_iteration()
        self.assertEqual(tracker.phase_iterations(), 1)
        tracker.record_iteration()
        tracker.record_iteration()
        self.assertEqual(tracker.phase_iterations(), 3)

    def test_phase_tool_calls_start_at_zero(self) -> None:
        tracker = PhaseTracker()
        self.assertEqual(tracker.phase_tool_calls(), 0)

    def test_record_tool_call_increments_counter(self) -> None:
        tracker = PhaseTracker()
        tracker.record_tool_call()
        self.assertEqual(tracker.phase_tool_calls(), 1)
        tracker.record_tool_call()
        self.assertEqual(tracker.phase_tool_calls(), 2)

    def test_default_phase_is_plan(self) -> None:
        tracker = PhaseTracker()
        self.assertEqual(tracker.current_phase, Phase.PLAN)


class PhaseTrackerCostTests(unittest.TestCase):
    def test_phase_cost_cents_returns_zero_initially(self) -> None:
        tracker = PhaseTracker()
        self.assertEqual(tracker.phase_cost_cents(50.0), 50.0)
        tracker.set_cost_start(0.0)
        self.assertEqual(tracker.phase_cost_cents(50.0), 50.0)

    def test_phase_cost_cents_delta_from_start(self) -> None:
        tracker = PhaseTracker()
        tracker.set_cost_start(100.0)
        self.assertEqual(tracker.phase_cost_cents(150.0), 50.0)
        self.assertEqual(tracker.phase_cost_cents(200.0), 100.0)

    def test_phase_cost_cents_never_negative(self) -> None:
        tracker = PhaseTracker()
        tracker.set_cost_start(200.0)
        self.assertEqual(tracker.phase_cost_cents(100.0), 0.0)


class PhaseTrackerTransitionTests(unittest.TestCase):
    def test_transition_resets_counters(self) -> None:
        tracker = PhaseTracker()
        tracker.record_iteration()
        tracker.record_iteration()
        tracker.record_tool_call()
        self.assertEqual(tracker.phase_iterations(), 2)
        self.assertEqual(tracker.phase_tool_calls(), 1)

        tracker.transition(Phase.EXECUTE)
        self.assertEqual(tracker.current_phase, Phase.EXECUTE)
        self.assertEqual(tracker.phase_iterations(), 0)
        self.assertEqual(tracker.phase_tool_calls(), 0)

    def test_transition_preserves_cost_start(self) -> None:
        tracker = PhaseTracker()
        tracker.set_cost_start(0.0)
        tracker.transition(Phase.EXECUTE, total_cost_cents=150.0)
        self.assertEqual(tracker.phase_cost_cents(200.0), 50.0)

    def test_transition_does_not_affect_other_phases(self) -> None:
        tracker = PhaseTracker()
        tracker.record_iteration()
        tracker.record_iteration()
        self.assertEqual(tracker.phase_iterations(), 2)

        tracker.transition(Phase.EXECUTE)
        self.assertEqual(tracker.phase_iterations(), 0)

        tracker.transition(Phase.PLAN)
        self.assertEqual(tracker.phase_iterations(), 0)


class AgentRunnerPhaseBudgetIntegrationTests(unittest.TestCase):
    @staticmethod
    def _make_phase_budget_runner(
        phase_budgets: dict[Phase, PhaseBudget],
        max_iterations: int = 25,
        max_tool_calls: int = 25,
    ):
        from teaagent.audit import AuditLogger
        from teaagent.budget import RunBudget
        from teaagent.phase_tracker import PhaseTracker
        from teaagent.runner import AgentRunner
        from teaagent.tools import ToolAnnotations, ToolRegistry

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
            annotations=ToolAnnotations(
                read_only=True, destructive=False, idempotent=True
            ),
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

    def test_phase_iteration_budget_enforced(self) -> None:
        from teaagent.runner import FinalAnswer, ToolRequest

        runner = self._make_phase_budget_runner(
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
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.iterations, 2)

        runner2 = self._make_phase_budget_runner(
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
        self.assertEqual(result2.status, 'completed')
        self.assertEqual(result2.iterations, 1)

    def test_phase_iteration_budget_exceeds_before_overall(self) -> None:
        from teaagent.runner import ToolRequest

        runner = self._make_phase_budget_runner(
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
        self.assertIn('failed', result.status)
        self.assertIn('iteration budget exceeded', result.error_message or '')

    def test_phase_tool_call_budget_enforced(self) -> None:
        from teaagent.runner import ToolRequest

        runner = self._make_phase_budget_runner(
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
        self.assertIn('failed', result.status)
        self.assertIn('tool-call budget exceeded', result.error_message or '')

    def test_phase_cost_budget_enforced(self) -> None:
        from teaagent.runner import FinalAnswer

        runner = self._make_phase_budget_runner(
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
        self.assertIn('failed', result.status)
        self.assertIn('cost budget exceeded', result.error_message or '')

    def test_phase_budget_warning_audit_event_emitted(self) -> None:
        from teaagent.runner import ToolRequest

        runner = self._make_phase_budget_runner(
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
        self.assertEqual(len(warning_events), 1)
        event = warning_events[0]
        self.assertEqual(event.payload['phase'], 'plan')
        self.assertEqual(event.payload['metric'], 'iterations')
        self.assertEqual(event.payload['limit'], 1)
        self.assertGreater(event.payload['current'], 1)

    def test_no_phase_budget_causes_no_phase_enforcement(self) -> None:
        from teaagent.runner import FinalAnswer

        runner = self._make_phase_budget_runner(
            phase_budgets={}, max_iterations=10, max_tool_calls=10
        )

        result = runner.run(
            task='test',
            decide=lambda ctx: FinalAnswer(content='done'),
            run_id='run-no-phase',
        )
        self.assertEqual(result.status, 'completed')
        self.assertGreater(result.iterations, 0)

    def test_different_phase_has_different_budget(self) -> None:
        from teaagent.runner import FinalAnswer, ToolRequest

        runner = self._make_phase_budget_runner(
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
        self.assertEqual(result.status, 'completed')
        self.assertGreater(result.iterations, 1)


if __name__ == '__main__':
    unittest.main()
