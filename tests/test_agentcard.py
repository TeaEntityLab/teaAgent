from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent.agentcard import (
    AgentCard,
    InMemoryAgentRegistry,
    build_self_card,
)


class AgentCardTests(unittest.TestCase):
    def _card(self, **kwargs) -> AgentCard:
        defaults = dict(
            name='test-agent',
            version='1.0.0',
            description='desc',
            capabilities=frozenset(['tool_execution']),
            tools=('read', 'write'),
        )
        defaults.update(kwargs)
        return AgentCard(**defaults)  # type: ignore[arg-type]

    def test_to_dict_round_trips(self) -> None:
        card = self._card()
        d = card.to_dict()
        self.assertEqual(d['name'], 'test-agent')
        self.assertEqual(d['tools'], ['read', 'write'])
        self.assertIn('tool_execution', d['capabilities'])

    def test_from_dict_round_trips(self) -> None:
        card = self._card(endpoint='https://agent.test')
        restored = AgentCard.from_dict(card.to_dict())
        self.assertEqual(restored.name, card.name)
        self.assertEqual(restored.version, card.version)
        self.assertEqual(restored.endpoint, card.endpoint)
        self.assertEqual(restored.tools, card.tools)
        self.assertEqual(restored.capabilities, card.capabilities)

    def test_from_dict_handles_missing_optional_fields(self) -> None:
        card = AgentCard.from_dict({'name': 'x', 'version': '0.1'})
        self.assertEqual(card.description, '')
        self.assertIsNone(card.endpoint)
        self.assertEqual(card.tools, ())
        self.assertEqual(card.capabilities, frozenset())

    def test_capabilities_sorted_in_to_dict(self) -> None:
        card = self._card(capabilities=frozenset(['z_cap', 'a_cap']))
        d = card.to_dict()
        self.assertEqual(d['capabilities'], ['a_cap', 'z_cap'])


class InMemoryAgentRegistryTests(unittest.TestCase):
    def _card(self, name: str, caps=None, tools=()) -> AgentCard:
        return AgentCard(
            name=name,
            version='1.0',
            description='',
            capabilities=frozenset(caps or []),
            tools=tuple(tools),
        )

    def test_register_and_get(self) -> None:
        registry = InMemoryAgentRegistry()
        card = self._card('agent-a')
        registry.register(card)
        self.assertIs(registry.get('agent-a'), card)

    def test_register_overwrites(self) -> None:
        registry = InMemoryAgentRegistry()
        registry.register(self._card('a'))
        updated = self._card('a', caps=['new_cap'])
        registry.register(updated)
        self.assertIn('new_cap', registry.get('a').capabilities)  # type: ignore[union-attr]

    def test_deregister_removes(self) -> None:
        registry = InMemoryAgentRegistry()
        registry.register(self._card('a'))
        registry.deregister('a')
        self.assertIsNone(registry.get('a'))

    def test_deregister_missing_is_noop(self) -> None:
        InMemoryAgentRegistry().deregister('ghost')

    def test_list_cards(self) -> None:
        registry = InMemoryAgentRegistry()
        registry.register(self._card('a'))
        registry.register(self._card('b'))
        names = {c.name for c in registry.list_cards()}
        self.assertEqual(names, {'a', 'b'})

    def test_find_by_capability(self) -> None:
        registry = InMemoryAgentRegistry()
        registry.register(self._card('a', caps=['search', 'read']))
        registry.register(self._card('b', caps=['write']))
        result = registry.find_by_capability('search')
        self.assertEqual([c.name for c in result], ['a'])

    def test_find_by_capability_empty(self) -> None:
        registry = InMemoryAgentRegistry()
        self.assertEqual(registry.find_by_capability('nope'), [])

    def test_find_by_tool(self) -> None:
        registry = InMemoryAgentRegistry()
        registry.register(self._card('a', tools=['read_file', 'write_file']))
        registry.register(self._card('b', tools=['shell']))
        result = registry.find_by_tool('shell')
        self.assertEqual([c.name for c in result], ['b'])


class BuildSelfCardTests(unittest.TestCase):
    def _fake_registry(self, tool_names: list) -> object:
        class FakeRegistry:
            def mcp_metadata(self):
                return [{'name': n} for n in tool_names]

        return FakeRegistry()

    def test_includes_standard_capabilities(self) -> None:
        reg = self._fake_registry(['read', 'write'])
        card = build_self_card('my-agent', '1.2.3', reg)
        self.assertIn('tool_execution', card.capabilities)
        self.assertIn('audit_logging', card.capabilities)
        self.assertIn('budget_enforcement', card.capabilities)

    def test_tools_match_registry(self) -> None:
        reg = self._fake_registry(['alpha', 'beta'])
        card = build_self_card('a', '1.0', reg)
        self.assertEqual(card.tools, ('alpha', 'beta'))

    def test_endpoint_propagated(self) -> None:
        reg = self._fake_registry([])
        card = build_self_card('a', '1.0', reg, endpoint='https://ep.test')
        self.assertEqual(card.endpoint, 'https://ep.test')

    def test_extra_capabilities_merged(self) -> None:
        reg = self._fake_registry([])
        card = build_self_card('a', '1.0', reg, extra_capabilities=frozenset(['rag']))
        self.assertIn('rag', card.capabilities)


class AgentCardCLITests(unittest.TestCase):
    def test_agent_card_prints_json(self) -> None:
        from teaagent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['agent', 'card', '--root', tmp])

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn('name', payload)
        self.assertIn('tools', payload)
        self.assertIn('capabilities', payload)
        self.assertIn('tool_execution', payload['capabilities'])

    def test_agent_card_with_custom_name_and_endpoint(self) -> None:
        from teaagent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        'agent',
                        'card',
                        '--root',
                        tmp,
                        '--agent-name',
                        'my-custom-agent',
                        '--endpoint',
                        'https://agent.example.com',
                    ]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload['name'], 'my-custom-agent')
        self.assertEqual(payload['endpoint'], 'https://agent.example.com')


if __name__ == '__main__':
    unittest.main()
