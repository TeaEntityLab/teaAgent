"""Test module for ANP (Agent Network Protocol) adapter integration.

This module tests the ANP adapter system, which enables federated agent communication
and task delegation across network boundaries. The ANP adapter provides bidirectional
routing, governed service execution, and integration with external agent networks.

Key concepts tested:
- Inbound Adapter: Handles incoming tasks from remote ANP peers
- Outbound Client: Sends tasks to remote ANP peers via transport layer
- Bidirectional Router: Auto-selects local execution with remote fallback
- Governed Service: Enforces tool governance (approvals, budgets) on ANP requests
- Budget Enforcement: ANP operations respect runtime budget limits
- Content Extraction: Parses provider-specific response formats (e.g., OpenCodeZen Go Kimi)

Acceptance Criteria:
- AC1: ANPInboundAdapter routes tasks to local handlers and returns results
- AC2: ANPBidirectionalRouter prefers local execution, falls back to remote on failure
- AC3: Remote routing requires explicit endpoint configuration
- AC4: Destructive tool calls via ANP require approval before execution
- AC5: ANP operations enforce budget limits (max_tool_calls, etc.)
- AC6: Audit trail records ANP-specific events (anp_inbound_started, anp_outbound_started)
- AC7: Content extraction works for provider-specific response formats

Technical Details:
- ANPInboundAdapter wraps local task handlers with ANP protocol
- ANPOutboundClient uses transport function to send tasks to remote endpoints
- ANPBidirectionalRouter implements auto-routing with fallback logic
- ANPGovernedService integrates ToolRegistry, AuditLogger, and RunBudget
- Tool governance (destructive flag) triggers approval workflow for ANP requests
- Budget violations raise BudgetExceededError and record audit events
- _extract_openai_content handles provider-specific response parsing

References:
- ANP protocol spec: /docs/specs/anp_protocol.md
- Federation architecture: /docs/architecture/federation.md
- Tool governance: /docs/security/tool_governance.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teaagent import (
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
from teaagent.llm._extract import _extract_openai_content
from teaagent.types import BudgetExceededError

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


def _build_registry(*, destructive: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='pilot_echo',
        description='Echo value for ANP acceptance.',
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


def test_anp_inbound_to_local_execution_flow() -> None:
    inbound = ANPInboundAdapter(
        lambda task, context: f'local:{task}:{context.get("mode")}'
    )

    result = inbound.handle_task({'task': 'analyze', 'context': {'mode': 'safe'}})

    assert result == {'status': 'ok', 'output': 'local:analyze:safe'}


def test_anp_bidirectional_auto_prefers_local_then_fallback_remote() -> None:
    local_calls: list[tuple[str, dict[str, object]]] = []
    remote_calls: list[tuple[str, str, dict[str, object]]] = []

    def local_runner(task: str, context: dict[str, object]) -> str:
        local_calls.append((task, context))
        if context.get('fail_local'):
            raise RuntimeError('local unavailable')
        return f'local-ok:{task}'

    def remote_transport(
        endpoint: str, task: str, context: dict[str, object]
    ) -> dict[str, object]:
        remote_calls.append((endpoint, task, context))
        return {'output': f'remote-ok:{task}', 'agent_name': 'remote-anp-peer'}

    router = ANPBidirectionalRouter(
        local_runner=local_runner,
        outbound_client=ANPOutboundClient(transport=remote_transport),
    )

    local_result = router.route(
        task='build',
        route='auto',
        context={'fail_local': False},
        remote_endpoint='http://anp-peer',
    )
    fallback_result = router.route(
        task='test',
        route='auto',
        context={'fail_local': True},
        remote_endpoint='http://anp-peer',
    )

    assert local_result.source == 'local'
    assert local_result.fallback_used is False
    assert local_result.output == 'local-ok:build'
    assert fallback_result.source == 'remote'
    assert fallback_result.fallback_used is True
    assert fallback_result.output == 'remote-ok:test'
    assert fallback_result.agent_name == 'remote-anp-peer'
    assert len(local_calls) == 2
    assert len(remote_calls) == 1


def test_anp_remote_route_requires_endpoint() -> None:
    router = ANPBidirectionalRouter(
        local_runner=lambda task, context: 'local-ok',
        outbound_client=ANPOutboundClient(
            transport=lambda endpoint, task, context: {'output': 'remote-ok'}
        ),
    )

    with pytest.raises(ANPAdapterError):
        router.route(task='ship', route='remote')


def test_anp_governed_inbound_destructive_requires_approval() -> None:
    audit = AuditLogger()
    service = ANPGovernedService(
        registry=_build_registry(destructive=True), audit=audit
    )

    result = service.handle_inbound(
        {
            'task': 'mutate',
            'correlation_id': 'accept-anp-1',
            'peer_endpoint': 'http://peer',
            'tool_request': {
                'tool_name': 'pilot_echo',
                'arguments': {'value': 'delete'},
                'call_id': 'call-accept-1',
            },
        }
    )

    assert result['status'] == 'pending_approval'
    assert result['approval']['call_id'] == 'call-accept-1'
    federation_events = [
        event for event in audit.events if event.event_type.startswith('anp_')
    ]
    assert federation_events
    assert federation_events[0].payload['anp_correlation_id'] == 'accept-anp-1'
    assert 'tool_call_pending_approval' in [e.event_type for e in audit.events]


def test_anp_governed_outbound_budget_and_audit() -> None:
    audit = AuditLogger()
    service = ANPGovernedService(
        registry=_build_registry(),
        audit=audit,
        budget=RunBudget(max_tool_calls=0),
        outbound_client=ANPOutboundClient(
            transport=lambda endpoint, task, context: {'output': 'remote'}
        ),
    )

    with pytest.raises(BudgetExceededError):
        service.route(
            task='delegate',
            route='remote',
            remote_endpoint='http://anp-peer',
            correlation_id='accept-anp-2',
        )

    assert 'anp_outbound_started' in [e.event_type for e in audit.events]


def test_opencodezen_go_kimi_fixture_extracts_reasoning_content() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / 'fixtures'
        / 'opencodezen_go_kimi_response.json'
    )
    payload = json.loads(fixture.read_text(encoding='utf-8'))
    content = _extract_openai_content('opencodezen-go', payload)
    assert content == 'kimi reasoning trace omitted'
