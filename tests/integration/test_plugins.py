"""IT: Plugin loader via entry-points.

load_plugins() scans the 'teaagent.tools' entry-point group and calls each
registered callable with the ToolRegistry.  Failing plugins are isolated and
do not crash the system.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from teaagent.plugins import PLUGIN_GROUP, PluginLoadResult, load_plugins
from teaagent.tools import ToolAnnotations, ToolRegistry


def _make_registrar(name: str):
    """Return a plugin callable that registers one tool named *name*."""

    def register(registry: ToolRegistry) -> None:
        registry.register(
            name=name,
            description=f'Plugin tool {name}',
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object', 'properties': {}},
            annotations=ToolAnnotations(read_only=True),
            handler=lambda _: {},
        )

    return register


def test_no_plugins_returns_empty(tmp_path):
    registry = ToolRegistry()
    with patch('teaagent.plugins._entry_points', return_value=[]):
        result = load_plugins(registry)
    assert result.loaded == []
    assert result.failed == []


def test_single_plugin_registers_tool():
    registry = ToolRegistry()
    ep = MagicMock()
    ep.name = 'my_plugin'
    ep.load.return_value = _make_registrar('plugin_echo')

    with patch('teaagent.plugins._entry_points', return_value=[ep]):
        result = load_plugins(registry)

    assert result.loaded == ['my_plugin']
    assert result.failed == []
    assert registry.get('plugin_echo') is not None


def test_multiple_plugins_all_loaded():
    registry = ToolRegistry()
    eps = []
    for i in range(3):
        ep = MagicMock()
        ep.name = f'plugin_{i}'
        ep.load.return_value = _make_registrar(f'tool_{i}')
        eps.append(ep)

    with patch('teaagent.plugins._entry_points', return_value=eps):
        result = load_plugins(registry)

    assert len(result.loaded) == 3
    assert result.failed == []


def test_failing_plugin_isolated():
    registry = ToolRegistry()

    def bad_plugin(reg: ToolRegistry) -> None:
        raise RuntimeError('plugin exploded')

    ep_good = MagicMock()
    ep_good.name = 'good'
    ep_good.load.return_value = _make_registrar('good_tool')

    ep_bad = MagicMock()
    ep_bad.name = 'bad'
    ep_bad.load.return_value = bad_plugin

    with patch('teaagent.plugins._entry_points', return_value=[ep_good, ep_bad]):
        result = load_plugins(registry)

    assert 'good' in result.loaded
    assert 'bad' in result.failed
    # good tool still registered despite bad plugin
    assert registry.get('good_tool') is not None


def test_failing_load_call_isolated():
    """ep.load() itself raises — must be isolated."""
    registry = ToolRegistry()
    ep = MagicMock()
    ep.name = 'broken_ep'
    ep.load.side_effect = ImportError('missing dep')

    with patch('teaagent.plugins._entry_points', return_value=[ep]):
        result = load_plugins(registry)

    assert result.loaded == []
    assert 'broken_ep' in result.failed


def test_custom_group_used():
    registry = ToolRegistry()
    captured_group: list[str] = []

    def fake_eps(group: str):
        captured_group.append(group)
        return []

    with patch('teaagent.plugins._entry_points', side_effect=fake_eps):
        load_plugins(registry, group='my.custom.group')

    assert captured_group == ['my.custom.group']


def test_default_group_is_teaagent_tools():
    assert PLUGIN_GROUP == 'teaagent.tools'


def test_plugin_load_result_ok():
    r = PluginLoadResult(loaded=['a', 'b'], failed=[])
    assert r.ok
    assert len(r.loaded) == 2


def test_plugin_load_result_not_ok_when_failures():
    r = PluginLoadResult(loaded=['a'], failed=['b'])
    assert not r.ok
