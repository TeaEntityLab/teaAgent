from __future__ import annotations

import pytest

from teaagent.types import ToolAnnotations, ToolRegistry, ToolValidationError


def _valid_instance() -> ToolRegistry:
    return ToolRegistry()


def _valid_kwargs(**overrides):
    kwargs = dict(
        name='my_tool',
        description='A test tool.',
        input_schema={'type': 'object', 'properties': {}, 'required': []},
        output_schema={'type': 'object', 'properties': {}, 'required': []},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'ok': True},
    )
    kwargs.update(overrides)
    return kwargs


def test_register_and_get_by_name() -> None:
    registry = _valid_instance()
    registry.register(**_valid_kwargs())

    tool = registry.get('my_tool')
    assert tool.name == 'my_tool'
    assert tool.description == 'A test tool.'


def test_register_multiple_distinct_tools() -> None:
    registry = _valid_instance()
    registry.register(**_valid_kwargs(name='tool_a'))
    registry.register(**_valid_kwargs(name='tool_b'))
    registry.register(**_valid_kwargs(name='tool_c'))

    assert len(registry._tools) == 3


def test_register_rejects_empty_name() -> None:
    registry = _valid_instance()
    with pytest.raises(ValueError) as ctx:
        registry.register(**_valid_kwargs(name=''))
    assert 'non-empty' in str(ctx.value)


def test_register_rejects_name_with_whitespace() -> None:
    registry = _valid_instance()
    with pytest.raises(ValueError) as ctx:
        registry.register(**_valid_kwargs(name='bad name'))
    assert 'no spaces' in str(ctx.value)


def test_register_rejects_duplicate_name() -> None:
    registry = _valid_instance()
    registry.register(**_valid_kwargs(name='dup'))

    with pytest.raises(ValueError) as ctx:
        registry.register(**_valid_kwargs(name='dup'))
    assert 'already registered' in str(ctx.value)


def test_register_rejects_empty_description() -> None:
    registry = _valid_instance()
    with pytest.raises(ValueError) as ctx:
        registry.register(**_valid_kwargs(description=''))
    assert 'description is required' in str(ctx.value)


def test_get_unknown_tool_raises_key_error() -> None:
    registry = _valid_instance()
    with pytest.raises(KeyError) as ctx:
        registry.get('nonexistent')
    assert 'not registered' in str(ctx.value)


def test_execute_validates_input_and_runs_handler() -> None:
    registry = _valid_instance()
    registry.register(
        **_valid_kwargs(
            name='echo',
            input_schema={
                'type': 'object',
                'properties': {'message': {'type': 'string'}},
                'required': ['message'],
            },
            output_schema={
                'type': 'object',
                'properties': {'reply': {'type': 'string'}},
                'required': ['reply'],
            },
            handler=lambda args: {'reply': args['message']},
        )
    )

    result = registry.execute('echo', {'message': 'hello'})
    assert result == {'reply': 'hello'}


def test_execute_validates_array_output_items() -> None:
    registry = _valid_instance()
    registry.register(
        **_valid_kwargs(
            name='bad_array',
            output_schema={
                'type': 'object',
                'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
                'required': ['items'],
            },
            handler=lambda args: {'items': ['ok', 1]},
        )
    )

    with pytest.raises(ToolValidationError) as ctx:
        registry.execute('bad_array', {})
    assert 'tool.bad_array.output.items[1]' in str(ctx.value)


def test_execute_unknown_tool_raises_key_error() -> None:
    registry = _valid_instance()
    with pytest.raises(KeyError):
        registry.execute('ghost', {})


def test_mcp_metadata_returns_list_of_tool_dicts() -> None:
    registry = _valid_instance()
    registry.register(**_valid_kwargs(name='tool_a'))
    registry.register(**_valid_kwargs(name='tool_b'))
    metadata = registry.mcp_metadata()

    assert len(metadata) == 2
    assert metadata[0]['name'] == 'tool_a'
    assert 'readOnlyHint' in metadata[0]['annotations']


def test_mcp_metadata_empty_registry() -> None:
    registry = _valid_instance()
    assert registry.mcp_metadata() == []
