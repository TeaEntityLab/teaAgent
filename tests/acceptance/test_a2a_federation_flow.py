from __future__ import annotations

import unittest

from teaagent.agentcard import (
    A2AClient,
    A2ADiscoveryServer,
    A2ADispatcher,
    AgentCard,
    FederatedAgentRegistry,
)


class A2AFederationFlowAcceptanceTests(unittest.TestCase):
    def test_federated_discovery_routes_by_capability_and_delegates(self) -> None:
        calls: list[tuple[str, dict]] = []

        def handler(task: str, context: dict) -> str:
            calls.append((task, context))
            return f'searched:{context["query"]}'

        card = AgentCard(
            name='search-agent',
            version='1.0.0',
            description='Search specialist',
            capabilities=frozenset({'search'}),
            tools=('workspace_search_text',),
        )
        with A2ADiscoveryServer(card, port=0, task_handler=handler) as server:
            base_url = server.base_url
            registry = FederatedAgentRegistry(
                ['http://127.0.0.1:1', base_url], ttl_seconds=60, timeout=1
            )
            errors = registry.refresh()
            dispatcher = A2ADispatcher(registry)

            result = dispatcher.dispatch_by_capability(
                'find docs',
                'search',
                runner=lambda task, routed_card: (
                    A2AClient.from_card(routed_card, timeout=5)
                    .delegate(task, context={'query': 'docs'})
                    .output
                ),
            )
            fetched = registry.get('search-agent')

        self.assertEqual(len(errors), 1)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.endpoint, base_url)
        self.assertEqual(result.agent_name, 'search-agent')
        self.assertEqual(result.routed_by_capability, 'search')
        self.assertEqual(result.output, 'searched:docs')
        self.assertEqual(calls, [('find docs', {'query': 'docs'})])


if __name__ == '__main__':
    unittest.main()
