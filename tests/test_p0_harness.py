from __future__ import annotations

import unittest

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


class P0HarnessTests(unittest.TestCase):
    def test_runner_executes_registered_tool_and_audits_result(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(), audit=audit)

        def decide(context):
            if not context['observations']:
                return ToolRequest(tool_name='pilot_echo', arguments={'value': 'ok'})
            return FinalAnswer(content=context['observations'][0]['result']['value'])

        result = runner.run(task='echo ok', decide=decide, run_id='run-1')

        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.final_answer.content, 'ok')
        self.assertIn(
            'tool_call_completed', [event.event_type for event in audit.events]
        )

    def test_destructive_tool_requires_exact_call_approval(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(destructive=True), audit=audit)

        def decide(_context):
            return ToolRequest(
                tool_name='pilot_echo',
                arguments={'value': 'delete'},
                call_id='call-1',
            )

        result = runner.run(task='destructive action', decide=decide, run_id='run-2')

        self.assertEqual(result.status, 'pending_approval')
        self.assertEqual(result.metadata['approval']['call_id'], 'call-1')
        pending = [
            event
            for event in audit.events
            if event.event_type == 'tool_call_pending_approval'
        ]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].payload['tool_name'], 'pilot_echo')
        self.assertEqual(pending[0].payload['annotations']['destructive'], True)
        self.assertIn('explicit approval', pending[0].payload['reason'])
        self.assertEqual(audit.events[-1].event_type, 'run_paused')

    def test_destructive_tool_can_be_approved_by_hitl_handler(self) -> None:
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

        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(approvals, ['call-hitl'])
        self.assertIn(
            'tool_call_approved', [event.event_type for event in audit.events]
        )

    def test_denied_hitl_approval_fails_without_tool_execution(self) -> None:
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

        self.assertEqual(result.status, 'failed:permission')
        self.assertEqual(result.tool_calls, 0)
        self.assertIn('tool_call_denied', [event.event_type for event in audit.events])

    def test_approved_destructive_tool_can_run(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=build_registry(destructive=True),
            audit=audit,
            approval_policy=ApprovalPolicy(frozenset({'call-1'})),
        )

        def decide(context):
            if not context['observations']:
                return ToolRequest(
                    tool_name='pilot_echo',
                    arguments={'value': 'approved'},
                    call_id='call-1',
                )
            return FinalAnswer(content='done')

        result = runner.run(task='approved action', decide=decide, run_id='run-3')

        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.tool_calls, 1)

    def test_iteration_budget_stops_non_terminating_agent(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=build_registry(),
            audit=audit,
            budget=RunBudget(max_iterations=2, max_tool_calls=5),
        )

        def decide(_context):
            return ToolRequest(tool_name='pilot_echo', arguments={'value': 'loop'})

        result = runner.run(task='loop forever', decide=decide, run_id='run-4')

        self.assertEqual(result.status, 'failed:model_logic')
        self.assertEqual(result.iterations, 2)

    def test_schema_rejects_unexpected_arguments(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(), audit=audit)

        def decide(_context):
            return ToolRequest(
                tool_name='pilot_echo',
                arguments={'value': 'ok', 'extra': 'blocked'},
            )

        result = runner.run(task='bad schema', decide=decide, run_id='run-5')

        self.assertEqual(result.status, 'failed:model_logic')

    def test_cost_budget_blocks_tool_after_decision_cost_update(self) -> None:
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

        self.assertEqual(result.status, 'failed:model_logic')
        self.assertEqual(result.tool_calls, 0)
        self.assertNotIn(
            'tool_call_started', [event.event_type for event in audit.events]
        )
        self.assertEqual(audit.events[-1].payload['cost_cents'], 2.0)

    def test_initial_observations_replayed_into_context(self) -> None:
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

        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(seen[0], replayed)
        run_started = next(e for e in audit.events if e.event_type == 'run_started')
        self.assertEqual(run_started.payload['replayed_observations'], 2)

    def test_initial_observations_count_against_tool_call_budget(self) -> None:
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

        self.assertEqual(result.status, 'failed:model_logic')
        self.assertEqual(result.tool_calls, 2)

    def test_cost_budget_blocks_final_after_decision_cost_update(self) -> None:
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

        self.assertEqual(result.status, 'failed:model_logic')
        self.assertIsNone(result.final_answer)
        self.assertNotIn('run_completed', [event.event_type for event in audit.events])


if __name__ == '__main__':
    unittest.main()
