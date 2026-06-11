from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from teaagent.agentcard import (
    AgentCard,
    InMemoryAgentRegistry,
    build_self_card,
)


def _card(**kwargs) -> AgentCard:
    defaults = dict(
        name='test-agent',
        version='1.0.0',
        description='desc',
        capabilities=frozenset(['tool_execution']),
        tools=('read', 'write'),
    )
    defaults.update(kwargs)
    return AgentCard(**defaults)


def test_to_dict_round_trips() -> None:
    card = _card()
    d = card.to_dict()
    assert d['name'] == 'test-agent'
    assert d['tools'] == ['read', 'write']
    assert 'tool_execution' in d['capabilities']


def test_from_dict_round_trips() -> None:
    card = _card(endpoint='https://agent.test')
    restored = AgentCard.from_dict(card.to_dict())
    assert restored.name == card.name
    assert restored.version == card.version
    assert restored.endpoint == card.endpoint
    assert restored.tools == card.tools
    assert restored.capabilities == card.capabilities


def test_from_dict_handles_missing_optional_fields() -> None:
    card = AgentCard.from_dict({'name': 'x', 'version': '0.1'})
    assert card.description == ''
    assert card.endpoint is None
    assert card.tools == ()
    assert card.capabilities == frozenset()


def test_capabilities_sorted_in_to_dict() -> None:
    card = _card(capabilities=frozenset(['z_cap', 'a_cap']))
    d = card.to_dict()
    assert d['capabilities'] == ['a_cap', 'z_cap']


def _card_registry(name: str, caps=None, tools=()) -> AgentCard:
    return AgentCard(
        name=name,
        version='1.0',
        description='',
        capabilities=frozenset(caps or []),
        tools=tuple(tools),
    )


def test_register_and_get() -> None:
    registry = InMemoryAgentRegistry()
    card = _card_registry('agent-a')
    registry.register(card)
    assert registry.get('agent-a') is card


def test_register_overwrites() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(_card_registry('a'))
    updated = _card_registry('a', caps=['new_cap'])
    registry.register(updated)
    assert 'new_cap' in registry.get('a').capabilities


def test_deregister_removes() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(_card_registry('a'))
    registry.deregister('a')
    assert registry.get('a') is None


def test_deregister_missing_is_noop() -> None:
    InMemoryAgentRegistry().deregister('ghost')


def test_list_cards() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(_card_registry('a'))
    registry.register(_card_registry('b'))
    names = {c.name for c in registry.list_cards()}
    assert names == {'a', 'b'}


def test_find_by_capability() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(_card_registry('a', caps=['search', 'read']))
    registry.register(_card_registry('b', caps=['write']))
    result = registry.find_by_capability('search')
    assert [c.name for c in result] == ['a']


def test_find_by_capability_empty() -> None:
    registry = InMemoryAgentRegistry()
    assert registry.find_by_capability('nope') == []


def test_find_by_tool() -> None:
    registry = InMemoryAgentRegistry()
    registry.register(_card_registry('a', tools=['read_file', 'write_file']))
    registry.register(_card_registry('b', tools=['shell']))
    result = registry.find_by_tool('shell')
    assert [c.name for c in result] == ['b']


def _fake_registry(tool_names: list) -> object:
    class FakeRegistry:
        def mcp_metadata(self):
            return [{'name': n} for n in tool_names]

    return FakeRegistry()


def test_includes_standard_capabilities() -> None:
    reg = _fake_registry(['read', 'write'])
    card = build_self_card('my-agent', '1.2.3', reg)
    assert 'tool_execution' in card.capabilities
    assert 'audit_logging' in card.capabilities
    assert 'budget_enforcement' in card.capabilities


def test_tools_match_registry() -> None:
    reg = _fake_registry(['alpha', 'beta'])
    card = build_self_card('a', '1.0', reg)
    assert card.tools == ('alpha', 'beta')


def test_endpoint_propagated() -> None:
    reg = _fake_registry([])
    card = build_self_card('a', '1.0', reg, endpoint='https://ep.test')
    assert card.endpoint == 'https://ep.test'


def test_extra_capabilities_merged() -> None:
    reg = _fake_registry([])
    card = build_self_card('a', '1.0', reg, extra_capabilities=frozenset(['rag']))
    assert 'rag' in card.capabilities


def test_agent_card_prints_json() -> None:
    from teaagent.cli import main

    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['agent', 'card', '--root', str(tmp_path)])

        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert 'name' in payload
        assert 'tools' in payload
        assert 'capabilities' in payload
        assert 'tool_execution' in payload['capabilities']
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_agent_card_with_custom_name_and_endpoint() -> None:
    from teaagent.cli import main

    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'agent',
                    'card',
                    '--root',
                    str(tmp_path),
                    '--agent-name',
                    'my-custom-agent',
                    '--endpoint',
                    'https://agent.example.com',
                ]
            )

        assert exit_code == 0
        payload = json.loads(output.getvalue())
        assert payload['name'] == 'my-custom-agent'
        assert payload['endpoint'] == 'https://agent.example.com'
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


# Negative test cases for AgentCard edge cases and error conditions


def test_from_dict_missing_required_name_field() -> None:
    """Test that missing required 'name' field raises KeyError."""
    with pytest.raises(KeyError):
        AgentCard.from_dict({'version': '1.0'})


def test_from_dict_with_empty_name() -> None:
    """Test that empty name is handled."""
    card = AgentCard.from_dict({'name': '', 'version': '1.0'})
    assert card.name == ''


def test_from_dict_with_none_values() -> None:
    """Test that None values are handled gracefully."""
    card = AgentCard.from_dict({'name': 'test', 'version': None, 'description': None})
    assert card.name == 'test'
    assert card.version == 'None'  # actual behavior - converts to string
    assert card.description == 'None'  # actual behavior - converts to string


def test_from_dict_with_invalid_capability_types() -> None:
    """Test that non-string capabilities are handled."""
    card = AgentCard.from_dict(
        {'name': 'test', 'capabilities': [123, None, 'valid_cap']}
    )
    # Should convert to strings or handle gracefully
    assert 'valid_cap' in card.capabilities


def test_from_dict_with_invalid_tool_types() -> None:
    """Test that non-string tools are handled."""
    card = AgentCard.from_dict({'name': 'test', 'tools': [123, None, 'valid_tool']})
    # Should convert to strings or handle gracefully
    assert 'valid_tool' in card.tools


def test_from_dict_with_malformed_metadata() -> None:
    """Test that malformed metadata is handled."""
    card = AgentCard.from_dict(
        {
            'name': 'test',
            'metadata': {'key': [1, 2, 3], 'nested': {'deep': 'value'}},
        }
    )
    assert card.metadata['key'] == [1, 2, 3]
    assert card.metadata['nested']['deep'] == 'value'


def test_from_dict_with_very_long_strings() -> None:
    """Test that very long strings are handled."""
    long_string = 'x' * 100000
    card = AgentCard.from_dict({'name': long_string, 'description': long_string})
    assert card.name == long_string
    assert card.description == long_string


def test_from_dict_with_special_characters() -> None:
    """Test that special characters are handled."""
    special_chars = {
        'name': 'test-agent\n\t\r',
        'description': '你好世界🌍 😀🎉',
        'version': '1.0\0',
    }
    card = AgentCard.from_dict(special_chars)
    assert '\n' in card.name
    assert '🌍' in card.description


def test_to_dict_round_trip_with_special_characters() -> None:
    """Test that special characters survive round-trip."""
    original = AgentCard(
        name='test\nagent',
        version='1.0',
        description='你好🌍',
        capabilities=frozenset(['cap\n1']),
        tools=('tool\t1',),
    )
    restored = AgentCard.from_dict(original.to_dict())
    assert restored.name == original.name
    assert restored.description == original.description


def test_from_dict_with_empty_capabilities_and_tools() -> None:
    """Test that empty capabilities and tools are handled."""
    card = AgentCard.from_dict({'name': 'test', 'capabilities': [], 'tools': []})
    assert len(card.capabilities) == 0
    assert len(card.tools) == 0


def test_from_dict_with_duplicate_capabilities() -> None:
    """Test that duplicate capabilities are deduplicated."""
    card = AgentCard.from_dict(
        {'name': 'test', 'capabilities': ['cap1', 'cap1', 'cap2']}
    )
    # frozenset should deduplicate
    assert len(card.capabilities) == 2


def test_from_dict_with_duplicate_tools() -> None:
    """Test that duplicate tools are preserved (tuple)."""
    card = AgentCard.from_dict({'name': 'test', 'tools': ['tool1', 'tool1', 'tool2']})
    # tuple preserves duplicates
    assert len(card.tools) == 3


def test_from_dict_with_invalid_endpoint() -> None:
    """Test that invalid endpoint URLs are handled."""
    card = AgentCard.from_dict({'name': 'test', 'endpoint': 'not-a-valid-url'})
    assert card.endpoint == 'not-a-valid-url'


def test_from_dict_with_numeric_name() -> None:
    """Test that numeric name is converted to string."""
    card = AgentCard.from_dict({'name': 123, 'version': '1.0'})
    assert card.name == '123'


# Negative test cases for InMemoryAgentRegistry error conditions


def test_register_with_none_name() -> None:
    """Test that card with None name is handled."""
    registry = InMemoryAgentRegistry()
    card = AgentCard(
        name='', version='1.0', description='', capabilities=frozenset(), tools=()
    )
    registry.register(card)
    # Should register with empty name
    assert registry.get('') is not None


def test_get_nonexistent_card() -> None:
    """Test that getting nonexistent card returns None."""
    registry = InMemoryAgentRegistry()
    assert registry.get('nonexistent') is None


def test_deregister_nonexistent_card() -> None:
    """Test that deregistering nonexistent card is no-op."""
    registry = InMemoryAgentRegistry()
    registry.deregister('nonexistent')  # Should not raise


def test_find_by_capability_with_empty_registry() -> None:
    """Test that find_by_capability on empty registry returns empty list."""
    registry = InMemoryAgentRegistry()
    assert registry.find_by_capability('any') == []


def test_find_by_capability_with_none_capability() -> None:
    """Test that None capability is handled."""
    registry = InMemoryAgentRegistry()
    card = AgentCard(
        name='test',
        version='1.0',
        description='',
        capabilities=frozenset(['cap1']),
        tools=(),
    )
    registry.register(card)
    result = registry.find_by_capability('nonexistent')
    assert result == []


def test_find_by_tool_with_empty_registry() -> None:
    """Test that find_by_tool on empty registry returns empty list."""
    registry = InMemoryAgentRegistry()
    assert registry.find_by_tool('any') == []


def test_list_cards_with_empty_registry() -> None:
    """Test that list_cards on empty registry returns empty list."""
    registry = InMemoryAgentRegistry()
    assert registry.list_cards() == []


def test_register_overwrites_with_different_capabilities() -> None:
    """Test that overwriting changes capabilities."""
    registry = InMemoryAgentRegistry()
    card1 = AgentCard(
        name='test',
        version='1.0',
        description='',
        capabilities=frozenset(['cap1']),
        tools=(),
    )
    card2 = AgentCard(
        name='test',
        version='2.0',
        description='',
        capabilities=frozenset(['cap2']),
        tools=(),
    )
    registry.register(card1)
    registry.register(card2)
    result = registry.get('test')
    assert result.version == '2.0'
    assert 'cap2' in result.capabilities


# ── Additional negative test cases for agentcard.py ───────────────────────────


def test_agent_card_with_very_long_name() -> None:
    """Test that very long name is handled."""
    long_name = 'a' * 10000
    card = AgentCard(
        name=long_name,
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert card.name == long_name
    # Should serialize correctly
    d = card.to_dict()
    assert d['name'] == long_name


def test_agent_card_with_very_long_version() -> None:
    """Test that very long version is handled."""
    long_version = '1.0.' + '0' * 10000
    card = AgentCard(
        name='test',
        version=long_version,
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert card.version == long_version


def test_agent_card_with_very_long_description() -> None:
    """Test that very long description is handled."""
    long_desc = 'a' * 100000
    card = AgentCard(
        name='test',
        version='1.0',
        description=long_desc,
        capabilities=frozenset(),
        tools=(),
    )
    assert card.description == long_desc


def test_agent_card_with_unicode_in_name() -> None:
    """Test that unicode characters in name are handled."""
    card = AgentCard(
        name='test-中文-🔐',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert '中文' in card.name
    assert '🔐' in card.name
    # Should round-trip through JSON
    restored = AgentCard.from_dict(card.to_dict())
    assert restored.name == card.name


def test_agent_card_with_unicode_in_capabilities() -> None:
    """Test that unicode characters in capabilities are handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(['中文能力', '🔐security']),
        tools=(),
    )
    assert '中文能力' in card.capabilities
    restored = AgentCard.from_dict(card.to_dict())
    assert '中文能力' in restored.capabilities


def test_agent_card_with_unicode_in_tools() -> None:
    """Test that unicode characters in tools are handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=('中文工具', '🔐encrypt'),
    )
    assert '中文工具' in card.tools
    restored = AgentCard.from_dict(card.to_dict())
    assert '中文工具' in restored.tools


def test_agent_card_with_empty_name() -> None:
    """Test that empty name is handled."""
    card = AgentCard(
        name='',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert card.name == ''


def test_agent_card_with_whitespace_name() -> None:
    """Test that whitespace-only name is handled."""
    card = AgentCard(
        name='   ',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert card.name == '   '


def test_agent_card_with_special_characters_in_name() -> None:
    """Test that special characters in name are handled."""
    card = AgentCard(
        name='test/\\:*?"<>|',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    assert card.name == 'test/\\:*?"<>|'


def test_agent_card_with_newline_in_description() -> None:
    """Test that newline in description is handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='line1\nline2\nline3',
        capabilities=frozenset(),
        tools=(),
    )
    assert '\n' in card.description
    restored = AgentCard.from_dict(card.to_dict())
    assert restored.description == card.description


def test_agent_card_from_dict_with_missing_name() -> None:
    """Test that missing name field raises appropriate error."""
    with pytest.raises(KeyError):
        AgentCard.from_dict({'version': '1.0'})


def test_agent_card_from_dict_with_invalid_version_type() -> None:
    """Test that invalid version type is handled."""
    # Should convert to string or handle gracefully
    card = AgentCard.from_dict({'name': 'test', 'version': 123})
    assert card.version == '123'


def test_agent_card_from_dict_with_capabilities_as_list() -> None:
    """Test that capabilities as list are converted to frozenset."""
    card = AgentCard.from_dict(
        {'name': 'test', 'version': '1.0', 'capabilities': ['cap1', 'cap2']}
    )
    assert isinstance(card.capabilities, frozenset)
    assert 'cap1' in card.capabilities


def test_agent_card_from_dict_with_tools_as_list() -> None:
    """Test that tools as list are converted to tuple."""
    card = AgentCard.from_dict(
        {'name': 'test', 'version': '1.0', 'tools': ['tool1', 'tool2']}
    )
    assert isinstance(card.tools, tuple)
    assert 'tool1' in card.tools


def test_agent_card_from_dict_with_none_endpoint() -> None:
    """Test that None endpoint is handled."""
    card = AgentCard.from_dict({'name': 'test', 'version': '1.0', 'endpoint': None})
    assert card.endpoint is None


def test_agent_card_from_dict_with_empty_endpoint() -> None:
    """Test that empty endpoint string is converted to None."""
    card = AgentCard.from_dict({'name': 'test', 'version': '1.0', 'endpoint': ''})
    assert card.endpoint is None


def test_agent_card_from_dict_with_invalid_url_endpoint() -> None:
    """Test that invalid URL endpoint is stored as-is."""
    card = AgentCard.from_dict(
        {'name': 'test', 'version': '1.0', 'endpoint': 'not-a-valid-url'}
    )
    assert card.endpoint == 'not-a-valid-url'


def test_agent_card_with_duplicate_capabilities() -> None:
    """Test that duplicate capabilities in frozenset are handled."""
    # Frozenset automatically deduplicates
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(['cap1', 'cap1', 'cap2']),
        tools=(),
    )
    assert len(card.capabilities) == 2


def test_agent_card_with_duplicate_tools() -> None:
    """Test that duplicate tools in tuple are preserved."""
    # Tuple preserves duplicates
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=('tool1', 'tool1', 'tool2'),
    )
    assert len(card.tools) == 3


def test_agent_card_metadata_with_none_values() -> None:
    """Test that None values in metadata are handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
        metadata={'key1': None, 'key2': 'value'},
    )
    assert card.metadata['key1'] is None
    assert card.metadata['key2'] == 'value'


def test_agent_card_metadata_with_nested_dict() -> None:
    """Test that nested dict in metadata is handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
        metadata={'nested': {'deep': {'value': 'test'}}},
    )
    assert card.metadata['nested']['deep']['value'] == 'test'


def test_agent_card_metadata_with_list_values() -> None:
    """Test that list values in metadata are handled."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
        metadata={'items': [1, 2, 3]},
    )
    assert card.metadata['items'] == [1, 2, 3]


def test_in_memory_registry_with_concurrent_access() -> None:
    """Test that registry handles concurrent access."""
    import threading

    registry = InMemoryAgentRegistry()

    def register_cards(worker_idx):
        for i in range(10):
            card = AgentCard(
                name=f'agent-{worker_idx}-{i}',
                version='1.0',
                description='desc',
                capabilities=frozenset(),
                tools=(),
            )
            registry.register(card)

    threads = [threading.Thread(target=register_cards, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have all cards registered
    assert len(registry.list_cards()) == 50


def test_in_memory_registry_get_with_case_sensitive_name() -> None:
    """Test that name lookup is case-sensitive."""
    registry = InMemoryAgentRegistry()
    card = AgentCard(
        name='TestAgent',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    registry.register(card)

    # Case-sensitive lookup
    assert registry.get('TestAgent') is card
    assert registry.get('testagent') is None
    assert registry.get('TESTAGENT') is None


def test_agent_card_to_dict_preserves_all_fields() -> None:
    """Test that to_dict includes all relevant fields."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(['cap1', 'cap2']),
        tools=('tool1', 'tool2'),
        endpoint='https://example.com',
        metadata={'key': 'value'},
    )
    d = card.to_dict()
    assert set(d.keys()) == {
        'name',
        'version',
        'description',
        'capabilities',
        'tools',
        'endpoint',
        'metadata',
    }


def test_agent_card_immutability() -> None:
    """Test that AgentCard is immutable (frozen)."""
    card = AgentCard(
        name='test',
        version='1.0',
        description='desc',
        capabilities=frozenset(),
        tools=(),
    )
    with pytest.raises(FrozenInstanceError):
        card.name = 'other'
    with pytest.raises(FrozenInstanceError):
        card.version = '2.0'
