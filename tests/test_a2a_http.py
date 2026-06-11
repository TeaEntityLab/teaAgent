from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from teaagent.agentcard import (
    A2AClient,
    A2ADiscoveryServer,
    A2ATaskResult,
    AgentCard,
    FederatedAgentRegistry,
)


def _card(name: str = 'test-agent', endpoint: str = '') -> AgentCard:
    return AgentCard(
        name=name,
        version='1.0.0',
        description='Test agent',
        capabilities=frozenset(['search']),
        tools=('file_read',),
        endpoint=endpoint or None,
    )


def test_serves_well_known_agent_json() -> None:
    card = _card()
    with A2ADiscoveryServer(card, port=0) as server:
        client = A2AClient(server.base_url, allow_http=True)
        fetched = client.fetch_card()
    assert fetched.name == card.name
    assert fetched.version == card.version
    assert 'search' in fetched.capabilities


def test_404_for_unknown_path() -> None:
    card = _card()
    with (
        A2ADiscoveryServer(card, port=0) as server,
        pytest.raises(urllib.error.HTTPError) as ctx,
    ):
        urllib.request.urlopen(f'{server.base_url}/unknown', timeout=5)
    assert ctx.value.code == 404


def test_port_is_assigned() -> None:
    card = _card()
    with A2ADiscoveryServer(card, port=0) as server:
        assert server.port > 0


def test_base_url_includes_port() -> None:
    card = _card()
    with A2ADiscoveryServer(card, port=0) as server:
        assert str(server.port) in server.base_url


def test_task_delegation_via_handler() -> None:
    card = _card()
    calls: list[tuple[str, dict]] = []

    def handler(task: str, context: dict) -> str:
        calls.append((task, context))
        return f'done:{task}'

    with A2ADiscoveryServer(card, port=0, task_handler=handler) as server:
        client = A2AClient(server.base_url, allow_http=True)
        result = client.delegate('run tests', context={'env': 'ci'})

    assert isinstance(result, A2ATaskResult)
    assert result.output == 'done:run tests'
    assert len(calls) == 1
    assert calls[0][0] == 'run tests'
    assert calls[0][1]['env'] == 'ci'


def test_no_task_handler_returns_404_on_post() -> None:
    card = _card()
    with A2ADiscoveryServer(card, port=0) as server:
        req = urllib.request.Request(
            f'{server.base_url}/a2a/task',
            data=b'{"task":"x"}',
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with pytest.raises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
    assert ctx.value.code == 404


def test_stop_is_idempotent() -> None:
    card = _card()
    server = A2ADiscoveryServer(card, port=0)
    server.start()
    server.stop()
    server.stop()  # should not raise


def test_from_card_uses_endpoint() -> None:
    card = _card(endpoint='http://example.internal:9000')
    client = A2AClient.from_card(card)
    assert client._endpoint == 'http://example.internal:9000'


def test_from_card_raises_without_endpoint() -> None:
    card = _card()
    with pytest.raises(ValueError):
        A2AClient.from_card(card)


def test_fetch_card_round_trip() -> None:
    original = _card(name='round-trip-agent')
    with A2ADiscoveryServer(original, port=0) as server:
        client = A2AClient(server.base_url, allow_http=True)
        fetched = client.fetch_card()
    assert fetched.name == 'round-trip-agent'
    assert 'file_read' in fetched.tools


def test_delegate_returns_task_result() -> None:
    card = _card()
    with A2ADiscoveryServer(
        card, port=0, task_handler=lambda t, c: 'finished'
    ) as server:
        result = A2AClient(server.base_url, allow_http=True).delegate('my task')
    assert result.output == 'finished'
    assert result.task == 'my task'


def test_delegate_default_empty_context() -> None:
    received: list[dict] = []

    def handler(task: str, ctx: dict) -> str:
        received.append(ctx)
        return 'ok'

    card = _card()
    with A2ADiscoveryServer(card, port=0, task_handler=handler) as server:
        A2AClient(server.base_url, allow_http=True).delegate('task')
    assert received[0] == {}


def test_get_card_from_remote() -> None:
    card = _card(name='remote-agent')
    with A2ADiscoveryServer(card, port=0) as server:
        registry = FederatedAgentRegistry(
            [server.base_url], ttl_seconds=60, allow_http=True
        )
        fetched = registry.get('remote-agent')
    assert fetched is not None
    assert fetched.name == 'remote-agent'


def test_list_cards_from_multiple_servers() -> None:
    card_a = _card(name='agent-alpha')
    card_b = _card(name='agent-beta')
    with (
        A2ADiscoveryServer(card_a, port=0) as srv_a,
        A2ADiscoveryServer(card_b, port=0) as srv_b,
    ):
        registry = FederatedAgentRegistry(
            [srv_a.base_url, srv_b.base_url], ttl_seconds=60, allow_http=True
        )
        names = {c.name for c in registry.list_cards()}
    assert 'agent-alpha' in names
    assert 'agent-beta' in names


def test_get_missing_returns_none() -> None:
    card = _card(name='only-one')
    with A2ADiscoveryServer(card, port=0) as server:
        registry = FederatedAgentRegistry(
            [server.base_url], ttl_seconds=60, allow_http=True
        )
        assert registry.get('does-not-exist') is None


def test_errors_on_unreachable_endpoint() -> None:
    registry = FederatedAgentRegistry(
        ['http://127.0.0.1:1'], ttl_seconds=60, timeout=1, allow_http=True
    )
    errors = registry.refresh()
    assert len(errors) == 1
    assert '127.0.0.1:1' in errors[0]


def test_stale_cache_refreshes() -> None:
    card = _card(name='cached-agent')
    with A2ADiscoveryServer(card, port=0) as server:
        registry = FederatedAgentRegistry(
            [server.base_url], ttl_seconds=0, allow_http=True
        )
        # First call: stale immediately (ttl=0)
        first = registry.get('cached-agent')
        # Second call: still stale, refreshes again
        second = registry.get('cached-agent')
    assert first is not None
    assert second is not None


def test_find_by_capability() -> None:
    card = _card(name='searcher')
    with A2ADiscoveryServer(card, port=0) as server:
        registry = FederatedAgentRegistry(
            [server.base_url], ttl_seconds=60, allow_http=True
        )
        found = registry.find_by_capability('search')
    assert len(found) == 1
    assert found[0].name == 'searcher'


def test_find_by_tool() -> None:
    card = _card(name='reader')
    with A2ADiscoveryServer(card, port=0) as server:
        registry = FederatedAgentRegistry(
            [server.base_url], ttl_seconds=60, allow_http=True
        )
        found = registry.find_by_tool('file_read')
    assert len(found) == 1
    assert found[0].name == 'reader'
