from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.agentcard import (
    A2ADispatcher,
    A2ATaskResult,
    AgentCard,
    SQLiteAgentRegistry,
)


def _card(name: str, caps=None, tools=()) -> AgentCard:
    return AgentCard(
        name=name,
        version='1.0',
        description=f'{name} agent',
        capabilities=frozenset(caps or []),
        tools=tuple(tools),
    )


class SQLiteAgentRegistryTests(unittest.TestCase):
    def test_register_and_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            card = _card('alpha', caps=['search'])
            reg.register(card)
            loaded = reg.get('alpha')
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.name, 'alpha')
            self.assertIn('search', loaded.capabilities)

    def test_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'agents.db'
            SQLiteAgentRegistry(path).register(_card('beta'))
            loaded = SQLiteAgentRegistry(path).get('beta')
            self.assertIsNotNone(loaded)

    def test_deregister_removes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            reg.register(_card('gamma'))
            reg.deregister('gamma')
            self.assertIsNone(reg.get('gamma'))

    def test_deregister_missing_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            SQLiteAgentRegistry(Path(tmp) / 'agents.db').deregister('ghost')

    def test_overwrite_upserts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            reg.register(_card('delta', caps=['old_cap']))
            reg.register(_card('delta', caps=['new_cap']))
            loaded = reg.get('delta')
            assert loaded is not None
            self.assertIn('new_cap', loaded.capabilities)
            self.assertNotIn('old_cap', loaded.capabilities)

    def test_list_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            reg.register(_card('a'))
            reg.register(_card('b'))
            names = {c.name for c in reg.list_cards()}
            self.assertEqual(names, {'a', 'b'})

    def test_find_by_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            reg.register(_card('a', caps=['search', 'read']))
            reg.register(_card('b', caps=['write']))
            result = reg.find_by_capability('search')
            self.assertEqual([c.name for c in result], ['a'])

    def test_find_by_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            reg.register(_card('a', tools=['file_read']))
            reg.register(_card('b', tools=['shell']))
            result = reg.find_by_tool('shell')
            self.assertEqual([c.name for c in result], ['b'])

    def test_round_trip_preserves_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
            original = AgentCard(
                name='full',
                version='2.1.0',
                description='Full card',
                capabilities=frozenset(['cap_a', 'cap_b']),
                tools=('tool_x', 'tool_y'),
                endpoint='https://agent.example.com',
                metadata={'owner': 'team-alpha'},
            )
            reg.register(original)
            loaded = reg.get('full')
            assert loaded is not None
            self.assertEqual(loaded.version, '2.1.0')
            self.assertEqual(loaded.endpoint, 'https://agent.example.com')
            self.assertEqual(loaded.metadata['owner'], 'team-alpha')
            self.assertEqual(loaded.tools, ('tool_x', 'tool_y'))


class A2ADispatcherTests(unittest.TestCase):
    def _registry_with(self, *cards: AgentCard) -> object:
        reg = {}
        for card in cards:
            reg[card.name] = card

        class FakeReg:
            def find_by_capability(self, cap: str):
                return [c for c in reg.values() if cap in c.capabilities]

            def get(self, name: str):
                return reg.get(name)

        return FakeReg()

    def _runner(self, response: str = 'dispatched') -> object:
        def run(task: str, card: AgentCard) -> str:
            return f'{response}:{card.name}'

        return run

    def test_dispatch_by_capability_routes_to_first_match(self) -> None:
        registry = self._registry_with(
            _card('a', caps=['search']),
            _card('b', caps=['write']),
        )
        dispatcher = A2ADispatcher(registry)
        result = dispatcher.dispatch_by_capability(
            'find docs', 'search', runner=self._runner()
        )
        self.assertIsInstance(result, A2ATaskResult)
        self.assertEqual(result.agent_name, 'a')
        self.assertEqual(result.routed_by_capability, 'search')

    def test_dispatch_by_capability_raises_when_no_match(self) -> None:
        dispatcher = A2ADispatcher(self._registry_with())
        with self.assertRaises(LookupError):
            dispatcher.dispatch_by_capability(
                'task', 'missing_cap', runner=self._runner()
            )

    def test_dispatch_by_name_routes_to_named_agent(self) -> None:
        registry = self._registry_with(_card('agent-x'))
        dispatcher = A2ADispatcher(registry)
        result = dispatcher.dispatch_by_name('task', 'agent-x', runner=self._runner())
        self.assertEqual(result.agent_name, 'agent-x')
        self.assertIsNone(result.routed_by_capability)

    def test_dispatch_by_name_raises_for_unknown_agent(self) -> None:
        dispatcher = A2ADispatcher(self._registry_with())
        with self.assertRaises(LookupError):
            dispatcher.dispatch_by_name('task', 'no-such-agent', runner=self._runner())


if __name__ == '__main__':
    unittest.main()
