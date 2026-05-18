from __future__ import annotations

import pytest

from teaagent.anp_adapter import (
    ANPAdapterError,
    ANPBidirectionalRouter,
    ANPInboundAdapter,
    ANPOutboundClient,
)


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
