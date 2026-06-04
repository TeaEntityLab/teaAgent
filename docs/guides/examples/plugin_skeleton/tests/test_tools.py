"""Tests for the example plugin's greeting tool."""

import pytest
from my_plugin.tools import register

from teaagent.tools import ToolRegistry


@pytest.fixture()
def registry() -> ToolRegistry:
    r = ToolRegistry()
    register(r)
    return r


def test_informal_greeting(registry: ToolRegistry) -> None:
    result = registry.call('my_plugin_greet', {'name': 'Alice'})
    assert result == {'greeting': 'Hello, Alice!'}


def test_formal_greeting(registry: ToolRegistry) -> None:
    result = registry.call('my_plugin_greet', {'name': 'Bob', 'formal': True})
    assert result == {'greeting': 'Good day, Bob.'}


def test_blank_name_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match='blank'):
        registry.call('my_plugin_greet', {'name': '  '})


def test_missing_name_raises(registry: ToolRegistry) -> None:
    with pytest.raises(KeyError):  # tool not registered
        registry.call('my_plugin_greet', {})


def test_tool_is_read_only(registry: ToolRegistry) -> None:
    meta = next(m for m in registry.mcp_metadata() if m['name'] == 'my_plugin_greet')
    assert meta['annotations']['readOnly'] is True
