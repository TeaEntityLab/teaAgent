"""Test module for A2A (Agent-to-Agent) federation flow.

This module tests the core functionality of the A2A federation system, which enables
discovery and delegation of work across multiple autonomous agents. The federation
system allows agents to register their capabilities, discover other agents by capability,
and dispatch tasks to the most appropriate agent.

Key concepts tested:
- Agent Discovery: Agents can register with a discovery server and be found by capability
- Capability-based Routing: Tasks are routed to agents based on their declared capabilities
- Federation Registry: Central registry that maintains agent endpoints and capabilities
- Task Delegation: Agents can delegate tasks to other agents in the federation

Acceptance Criteria:
- AC1: Discovery server can register an agent with its capabilities
- AC2: Registry can discover agents by capability (e.g., 'search')
- AC3: Dispatcher can route tasks to appropriate agents based on capability
- AC4: Client can successfully delegate tasks to discovered agents
- AC5: Federation handles network errors gracefully (unreachable endpoints)

Technical Details:
- Uses A2ADiscoveryServer for agent registration and discovery
- FederatedAgentRegistry maintains agent endpoints with TTL-based refresh
- A2ADispatcher routes tasks based on capability matching
- A2AClient handles task delegation to remote agents
- Supports both HTTP and local socket-based communication

References:
- Design doc: /docs/architecture/a2a_federation.md
- Agent Card spec: /docs/specs/agent_card.md
"""

from __future__ import annotations

import time

from teaagent.agentcard import (
    A2AClient,
    A2ADiscoveryServer,
    A2ADispatcher,
    AgentCard,
    FederatedAgentRegistry,
)
from test_support import skip_if_socket_bind_is_blocked


def test_federated_discovery_routes_by_capability_and_delegates() -> None:
    skip_if_socket_bind_is_blocked()
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
            ['http://127.0.0.1:1', base_url],
            ttl_seconds=60,
            timeout=1,
            allow_http=True,
        )
        errors = []
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            errors = registry.refresh()
            if registry.find_by_capability('search'):
                break
            time.sleep(0.05)
        dispatcher = A2ADispatcher(registry)

        result = dispatcher.dispatch_by_capability(
            'find docs',
            'search',
            runner=lambda task, routed_card: (
                A2AClient.from_card(routed_card, timeout=5, allow_http=True)
                .delegate(task, context={'query': 'docs'})
                .output
            ),
        )
        fetched = registry.get('search-agent')

    # Verify exactly one error occurred (from the invalid endpoint)
    assert len(errors) == 1, (
        f'Expected exactly 1 error from invalid endpoint, got {len(errors)}'
    )
    # Verify the agent was successfully discovered and registered
    assert fetched is not None, 'Expected search-agent to be discovered and registered'
    # Verify the discovered agent has the correct endpoint
    assert fetched.endpoint == base_url, (
        f'Expected endpoint to be {base_url}, got {fetched.endpoint}'
    )
    # Verify the dispatcher routed to the correct agent
    assert result.agent_name == 'search-agent', (
        f'Expected agent_name to be "search-agent", got {result.agent_name}'
    )
    # Verify routing was based on the correct capability
    assert result.routed_by_capability == 'search', (
        f'Expected routed_by_capability to be "search", got {result.routed_by_capability}'
    )
    # Verify the delegated task executed correctly
    assert result.output == 'searched:docs', (
        f'Expected output to be "searched:docs", got {result.output}'
    )
    # Verify the handler received the correct task and context
    assert calls == [('find docs', {'query': 'docs'})], (
        f'Expected handler to receive task "find docs" with query "docs", got {calls}'
    )
