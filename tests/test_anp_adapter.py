from __future__ import annotations

import unittest

from teaagent import (
    ApprovalPolicy,
    AuditLogger,
    RunBudget,
    ToolAnnotations,
    ToolRegistry,
)
from teaagent.anp_adapter import (
    ANPAdapterError,
    ANPBidirectionalRouter,
    ANPGovernedService,
    ANPInboundAdapter,
    ANPOutboundClient,
)
from teaagent.types import BudgetExceededError, PermissionMode

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
        description='Echo value for ANP governance tests.',
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


class ANPInboundAdapterTests(unittest.TestCase):
    def test_handle_task_success(self) -> None:
        adapter = ANPInboundAdapter(lambda task, context: f'ok:{task}:{context["x"]}')
        result = adapter.handle_task({'task': 'build', 'context': {'x': '1'}})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['output'], 'ok:build:1')

    def test_handle_task_requires_task(self) -> None:
        adapter = ANPInboundAdapter(lambda task, context: 'unused')
        with self.assertRaises(ANPAdapterError):
            adapter.handle_task({'context': {}})

    def test_handle_task_maps_execution_error(self) -> None:
        def _fail(task: str, context: dict[str, object]) -> str:
            raise RuntimeError('local failure')

        adapter = ANPInboundAdapter(_fail)
        result = adapter.try_handle_task({'task': 'test'})
        self.assertEqual(result['status'], 'error')
        self.assertIn('local failure', result['error'])


class ANPOutboundClientTests(unittest.TestCase):
    def test_delegate_uses_transport(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []

        def _transport(endpoint: str, task: str, context: dict[str, object]) -> dict:
            calls.append((endpoint, task, context))
            return {'output': 'remote done', 'agent_name': 'remote-a'}

        client = ANPOutboundClient(transport=_transport)
        result = client.delegate(
            endpoint='http://agent.example',
            task='ship',
            context={'env': 'ci'},
        )
        self.assertEqual(result.output, 'remote done')
        self.assertEqual(result.agent_name, 'remote-a')
        self.assertEqual(calls[0][1], 'ship')


class ANPBidirectionalRouterTests(unittest.TestCase):
    def test_auto_prefers_local(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: 'local ok',
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {'output': 'remote'}
            ),
        )
        result = router.route(task='run', route='auto', remote_endpoint='http://remote')
        self.assertEqual(result.source, 'local')
        self.assertEqual(result.output, 'local ok')

    def test_auto_falls_back_to_remote_when_local_fails(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: (_ for _ in ()).throw(
                RuntimeError('boom')
            ),
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {
                    'output': 'remote recovered',
                    'agent_name': 'remote-b',
                }
            ),
        )
        result = router.route(
            task='run',
            route='auto',
            remote_endpoint='http://remote',
            context={'k': 'v'},
        )
        self.assertEqual(result.source, 'remote')
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.output, 'remote recovered')

    def test_remote_route_requires_endpoint(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: 'local ok',
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {'output': 'remote'}
            ),
        )
        with self.assertRaises(ANPAdapterError):
            router.route(task='run', route='remote')


class ANPGovernedServiceTests(unittest.TestCase):
    def test_inbound_destructive_tool_requires_approval(self) -> None:
        audit = AuditLogger()
        service = ANPGovernedService(
            registry=build_registry(destructive=True),
            audit=audit,
        )
        result = service.handle_inbound(
            {
                'task': 'delete file',
                'correlation_id': 'anp-in-1',
                'tool_request': {
                    'tool_name': 'pilot_echo',
                    'arguments': {'value': 'x'},
                    'call_id': 'call-anp-1',
                },
            }
        )

        self.assertEqual(result['status'], 'pending_approval')
        self.assertEqual(result['correlation_id'], 'anp-in-1')
        self.assertEqual(result['approval']['call_id'], 'call-anp-1')
        event_types = [event.event_type for event in audit.events]
        self.assertIn('anp_inbound_received', event_types)
        self.assertIn('tool_call_pending_approval', event_types)
        self.assertIn('anp_inbound_completed', event_types)
        inbound_completed = [
            event
            for event in audit.events
            if event.event_type == 'anp_inbound_completed'
        ][0]
        self.assertTrue(inbound_completed.payload['approval_required'])

    def test_inbound_tool_executes_through_registry(self) -> None:
        audit = AuditLogger()
        service = ANPGovernedService(
            registry=build_registry(),
            audit=audit,
            approval_policy=ApprovalPolicy(
                permission_mode=PermissionMode.DANGER_FULL_ACCESS,
                allow_all_destructive=True,
                full_access_acknowledged=True,
            ),
        )
        result = service.handle_inbound(
            {
                'task': 'echo',
                'correlation_id': 'anp-in-2',
                'tool_request': {
                    'tool_name': 'pilot_echo',
                    'arguments': {'value': 'ok'},
                    'call_id': 'call-ok',
                },
            }
        )

        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['output'], "{'value': 'ok'}")
        self.assertIn('tool_call_completed', [e.event_type for e in audit.events])

    def test_outbound_delegation_enforces_budget(self) -> None:
        audit = AuditLogger()

        def remote_transport(
            endpoint: str, task: str, context: dict[str, object]
        ) -> dict[str, object]:
            return {'output': f'remote:{task}'}

        service = ANPGovernedService(
            registry=build_registry(),
            audit=audit,
            budget=RunBudget(max_tool_calls=0),
            outbound_client=ANPOutboundClient(transport=remote_transport),
        )

        with self.assertRaises(BudgetExceededError):
            service.route(
                task='delegate',
                route='remote',
                remote_endpoint='http://anp-peer',
                correlation_id='anp-out-1',
            )

    def test_outbound_timeout_records_audit_failure(self) -> None:
        audit = AuditLogger()

        def slow_transport(
            endpoint: str, task: str, context: dict[str, object]
        ) -> dict[str, object]:
            import time

            time.sleep(0.5)
            return {'output': 'late'}

        service = ANPGovernedService(
            registry=build_registry(),
            audit=audit,
            budget=RunBudget(max_tool_calls=2),
            outbound_client=ANPOutboundClient(
                transport=slow_transport, timeout_seconds=0.01
            ),
        )

        with self.assertRaises(ANPAdapterError):
            service.route(
                task='slow',
                route='remote',
                remote_endpoint='http://anp-peer',
                correlation_id='anp-out-2',
            )

        self.assertIn('anp_outbound_failed', [e.event_type for e in audit.events])


if __name__ == '__main__':
    unittest.main()
