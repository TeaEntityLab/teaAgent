from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

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


def test_register_and_get() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        card = _card('alpha', caps=['search'])
        reg.register(card)
        loaded = reg.get('alpha')
        assert loaded is not None
        assert loaded.name == 'alpha'
        assert 'search' in loaded.capabilities


def test_persists_across_instances() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'agents.db'
        SQLiteAgentRegistry(path).register(_card('beta'))
        loaded = SQLiteAgentRegistry(path).get('beta')
        assert loaded is not None


def test_deregister_removes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        reg.register(_card('gamma'))
        reg.deregister('gamma')
        assert reg.get('gamma') is None


def test_deregister_missing_is_noop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        SQLiteAgentRegistry(Path(tmp) / 'agents.db').deregister('ghost')


def test_overwrite_upserts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        reg.register(_card('delta', caps=['old_cap']))
        reg.register(_card('delta', caps=['new_cap']))
        loaded = reg.get('delta')
        assert loaded is not None
        assert 'new_cap' in loaded.capabilities
        assert 'old_cap' not in loaded.capabilities


def test_list_cards() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        reg.register(_card('a'))
        reg.register(_card('b'))
        names = {c.name for c in reg.list_cards()}
        assert names == {'a', 'b'}


def test_find_by_capability() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        reg.register(_card('a', caps=['search', 'read']))
        reg.register(_card('b', caps=['write']))
        result = reg.find_by_capability('search')
        assert [c.name for c in result] == ['a']


def test_find_by_tool() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        reg = SQLiteAgentRegistry(Path(tmp) / 'agents.db')
        reg.register(_card('a', tools=['file_read']))
        reg.register(_card('b', tools=['shell']))
        result = reg.find_by_tool('shell')
        assert [c.name for c in result] == ['b']


def test_round_trip_preserves_all_fields() -> None:
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
        assert loaded.version == '2.1.0'
        assert loaded.endpoint == 'https://agent.example.com'
        assert loaded.metadata['owner'] == 'team-alpha'
        assert loaded.tools == ('tool_x', 'tool_y')


def _registry_with(*cards: AgentCard) -> object:
    reg = {}
    for card in cards:
        reg[card.name] = card

    class FakeReg:
        def find_by_capability(self, cap: str):
            return [c for c in reg.values() if cap in c.capabilities]

        def get(self, name: str):
            return reg.get(name)

    return FakeReg()


def _runner(response: str = 'dispatched') -> object:
    def run(task: str, card: AgentCard) -> str:
        return f'{response}:{card.name}'

    return run


def test_dispatch_by_capability_routes_to_first_match() -> None:
    registry = _registry_with(
        _card('a', caps=['search']),
        _card('b', caps=['write']),
    )
    dispatcher = A2ADispatcher(registry)
    result = dispatcher.dispatch_by_capability('find docs', 'search', runner=_runner())
    assert isinstance(result, A2ATaskResult)
    assert result.agent_name == 'a'
    assert result.routed_by_capability == 'search'


def test_dispatch_by_capability_raises_when_no_match() -> None:
    dispatcher = A2ADispatcher(_registry_with())
    with pytest.raises(LookupError):
        dispatcher.dispatch_by_capability('task', 'missing_cap', runner=_runner())


def test_dispatch_by_name_routes_to_named_agent() -> None:
    registry = _registry_with(_card('agent-x'))
    dispatcher = A2ADispatcher(registry)
    result = dispatcher.dispatch_by_name('task', 'agent-x', runner=_runner())
    assert result.agent_name == 'agent-x'
    assert result.routed_by_capability is None


def test_dispatch_by_name_raises_for_unknown_agent() -> None:
    dispatcher = A2ADispatcher(_registry_with())
    with pytest.raises(LookupError):
        dispatcher.dispatch_by_name('task', 'no-such-agent', runner=_runner())
