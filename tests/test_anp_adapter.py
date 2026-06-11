from __future__ import annotations

import pytest

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


def test_handle_task_success() -> None:
    adapter = ANPInboundAdapter(lambda task, context: f'ok:{task}:{context["x"]}')
    result = adapter.handle_task({'task': 'build', 'context': {'x': '1'}})
    assert result['status'] == 'ok'
    assert result['output'] == 'ok:build:1'


def test_handle_task_requires_task() -> None:
    adapter = ANPInboundAdapter(lambda task, context: 'unused')
    with pytest.raises(ANPAdapterError):
        adapter.handle_task({'context': {}})


def test_handle_task_maps_execution_error() -> None:
    def _fail(task: str, context: dict[str, object]) -> str:
        raise RuntimeError('local failure')

    adapter = ANPInboundAdapter(_fail)
    result = adapter.try_handle_task({'task': 'test'})
    assert result['status'] == 'error'
    assert 'local failure' in result['error']


def test_delegate_uses_transport() -> None:
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
    assert result.output == 'remote done'
    assert result.agent_name == 'remote-a'
    assert calls[0][1] == 'ship'


def test_auto_prefers_local() -> None:
    router = ANPBidirectionalRouter(
        local_runner=lambda task, context: 'local ok',
        outbound_client=ANPOutboundClient(
            transport=lambda endpoint, task, context: {'output': 'remote'}
        ),
    )
    result = router.route(task='run', route='auto', remote_endpoint='http://remote')
    assert result.source == 'local'
    assert result.output == 'local ok'


def test_auto_falls_back_to_remote_when_local_fails() -> None:
    router = ANPBidirectionalRouter(
        local_runner=lambda task, context: (_ for _ in ()).throw(RuntimeError('boom')),
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
    assert result.source == 'remote'
    assert result.fallback_used
    assert result.output == 'remote recovered'


def test_remote_route_requires_endpoint() -> None:
    router = ANPBidirectionalRouter(
        local_runner=lambda task, context: 'local ok',
        outbound_client=ANPOutboundClient(
            transport=lambda endpoint, task, context: {'output': 'remote'}
        ),
    )
    with pytest.raises(ANPAdapterError):
        router.route(task='run', route='remote')


def test_inbound_destructive_tool_requires_approval() -> None:
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

    assert result['status'] == 'pending_approval'
    assert result['correlation_id'] == 'anp-in-1'
    assert result['approval']['call_id'] == 'call-anp-1'
    event_types = [event.event_type for event in audit.events]
    assert 'anp_inbound_received' in event_types
    assert 'tool_call_pending_approval' in event_types
    assert 'anp_inbound_completed' in event_types
    inbound_completed = [
        event for event in audit.events if event.event_type == 'anp_inbound_completed'
    ][0]
    assert inbound_completed.payload['approval_required']


def test_inbound_tool_executes_through_registry() -> None:
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

    assert result['status'] == 'ok'
    assert result['output'] == "{'value': 'ok'}"
    assert 'tool_call_completed' in [e.event_type for e in audit.events]


def test_outbound_delegation_enforces_budget() -> None:
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

    with pytest.raises(BudgetExceededError):
        service.route(
            task='delegate',
            route='remote',
            remote_endpoint='http://anp-peer',
            correlation_id='anp-out-1',
        )


def test_outbound_timeout_records_audit_failure() -> None:
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

    with pytest.raises(ANPAdapterError):
        service.route(
            task='slow',
            route='remote',
            remote_endpoint='http://anp-peer',
            correlation_id='anp-out-2',
        )

    assert 'anp_outbound_failed' in [e.event_type for e in audit.events]
