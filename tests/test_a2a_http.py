from __future__ import annotations

import unittest

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


class A2ADiscoveryServerTests(unittest.TestCase):
    def test_serves_well_known_agent_json(self) -> None:
        card = _card()
        with A2ADiscoveryServer(card, port=0) as server:
            client = A2AClient(server.base_url)
            fetched = client.fetch_card()
        self.assertEqual(fetched.name, card.name)
        self.assertEqual(fetched.version, card.version)
        self.assertIn('search', fetched.capabilities)

    def test_404_for_unknown_path(self) -> None:
        import urllib.error

        card = _card()
        with A2ADiscoveryServer(card, port=0) as server:
            import urllib.request

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f'{server.base_url}/unknown', timeout=5)
        self.assertEqual(ctx.exception.code, 404)

    def test_port_is_assigned(self) -> None:
        card = _card()
        with A2ADiscoveryServer(card, port=0) as server:
            self.assertGreater(server.port, 0)

    def test_base_url_includes_port(self) -> None:
        card = _card()
        with A2ADiscoveryServer(card, port=0) as server:
            self.assertIn(str(server.port), server.base_url)

    def test_task_delegation_via_handler(self) -> None:
        card = _card()
        calls: list[tuple[str, dict]] = []

        def handler(task: str, context: dict) -> str:
            calls.append((task, context))
            return f'done:{task}'

        with A2ADiscoveryServer(card, port=0, task_handler=handler) as server:
            client = A2AClient(server.base_url)
            result = client.delegate('run tests', context={'env': 'ci'})

        self.assertIsInstance(result, A2ATaskResult)
        self.assertEqual(result.output, 'done:run tests')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 'run tests')
        self.assertEqual(calls[0][1]['env'], 'ci')

    def test_no_task_handler_returns_404_on_post(self) -> None:
        import urllib.error
        import urllib.request

        card = _card()
        with A2ADiscoveryServer(card, port=0) as server:
            req = urllib.request.Request(
                f'{server.base_url}/a2a/task',
                data=b'{"task":"x"}',
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 404)

    def test_stop_is_idempotent(self) -> None:
        card = _card()
        server = A2ADiscoveryServer(card, port=0)
        server.start()
        server.stop()
        server.stop()  # should not raise


class A2AClientTests(unittest.TestCase):
    def test_from_card_uses_endpoint(self) -> None:
        card = _card(endpoint='http://example.internal:9000')
        client = A2AClient.from_card(card)
        self.assertEqual(client._endpoint, 'http://example.internal:9000')

    def test_from_card_raises_without_endpoint(self) -> None:
        card = _card()
        with self.assertRaises(ValueError):
            A2AClient.from_card(card)

    def test_fetch_card_round_trip(self) -> None:
        original = _card(name='round-trip-agent')
        with A2ADiscoveryServer(original, port=0) as server:
            client = A2AClient(server.base_url)
            fetched = client.fetch_card()
        self.assertEqual(fetched.name, 'round-trip-agent')
        self.assertIn('file_read', fetched.tools)

    def test_delegate_returns_task_result(self) -> None:
        card = _card()
        with A2ADiscoveryServer(
            card, port=0, task_handler=lambda t, c: 'finished'
        ) as server:
            result = A2AClient(server.base_url).delegate('my task')
        self.assertEqual(result.output, 'finished')
        self.assertEqual(result.task, 'my task')

    def test_delegate_default_empty_context(self) -> None:
        received: list[dict] = []

        def handler(task: str, ctx: dict) -> str:
            received.append(ctx)
            return 'ok'

        card = _card()
        with A2ADiscoveryServer(card, port=0, task_handler=handler) as server:
            A2AClient(server.base_url).delegate('task')
        self.assertEqual(received[0], {})


class FederatedAgentRegistryTests(unittest.TestCase):
    def test_get_card_from_remote(self) -> None:
        card = _card(name='remote-agent')
        with A2ADiscoveryServer(card, port=0) as server:
            registry = FederatedAgentRegistry([server.base_url], ttl_seconds=60)
            fetched = registry.get('remote-agent')
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.name, 'remote-agent')

    def test_list_cards_from_multiple_servers(self) -> None:
        card_a = _card(name='agent-alpha')
        card_b = _card(name='agent-beta')
        with (
            A2ADiscoveryServer(card_a, port=0) as srv_a,
            A2ADiscoveryServer(card_b, port=0) as srv_b,
        ):
            registry = FederatedAgentRegistry(
                [srv_a.base_url, srv_b.base_url], ttl_seconds=60
            )
            names = {c.name for c in registry.list_cards()}
        self.assertIn('agent-alpha', names)
        self.assertIn('agent-beta', names)

    def test_get_missing_returns_none(self) -> None:
        card = _card(name='only-one')
        with A2ADiscoveryServer(card, port=0) as server:
            registry = FederatedAgentRegistry([server.base_url], ttl_seconds=60)
            self.assertIsNone(registry.get('does-not-exist'))

    def test_errors_on_unreachable_endpoint(self) -> None:
        registry = FederatedAgentRegistry(
            ['http://127.0.0.1:1'], ttl_seconds=60, timeout=1
        )
        errors = registry.refresh()
        self.assertEqual(len(errors), 1)
        self.assertIn('127.0.0.1:1', errors[0])

    def test_stale_cache_refreshes(self) -> None:
        card = _card(name='cached-agent')
        with A2ADiscoveryServer(card, port=0) as server:
            registry = FederatedAgentRegistry([server.base_url], ttl_seconds=0)
            # First call: stale immediately (ttl=0)
            first = registry.get('cached-agent')
            # Second call: still stale, refreshes again
            second = registry.get('cached-agent')
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)

    def test_find_by_capability(self) -> None:
        card = _card(name='searcher')
        with A2ADiscoveryServer(card, port=0) as server:
            registry = FederatedAgentRegistry([server.base_url], ttl_seconds=60)
            found = registry.find_by_capability('search')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, 'searcher')

    def test_find_by_tool(self) -> None:
        card = _card(name='reader')
        with A2ADiscoveryServer(card, port=0) as server:
            registry = FederatedAgentRegistry([server.base_url], ttl_seconds=60)
            found = registry.find_by_tool('file_read')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, 'reader')


if __name__ == '__main__':
    unittest.main()
