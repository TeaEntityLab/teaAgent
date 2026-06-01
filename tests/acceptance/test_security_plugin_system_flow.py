"""Acceptance: plugin system discovery, registry, and manifest loading."""

from __future__ import annotations

import json

from teaagent.plugin_system import (
    AgentPlugin,
    CommandPlugin,
    PluginManifest,
    PluginRegistry,
    PluginType,
    discover_plugins,
    register_builtin_plugins,
)


class TestPluginManifest:
    def test_create_from_data(self):
        manifest = PluginManifest(
            name='test-cmd',
            version='1.0.0',
            plugin_type=PluginType.COMMAND,
            description='A test command',
        )
        assert manifest.name == 'test-cmd'
        assert manifest.plugin_type == PluginType.COMMAND
        assert manifest.author == 'unknown'
        assert manifest.entry_point is None

    def test_all_plugin_types(self):
        for ptype in PluginType:
            manifest = PluginManifest(
                name=f'p-{ptype.value}',
                version='1.0',
                plugin_type=ptype,
                description=f'{ptype.value} plugin',
            )
            assert manifest.plugin_type == ptype


class TestPluginRegistry:
    def test_register_and_get_command(self):
        registry = PluginRegistry()
        cmd = CommandPlugin(name='hello', description='Say hello', handler=lambda: None)
        registry.register_command(cmd)
        assert registry.get_command('hello') is cmd
        assert registry.get_command('nonexistent') is None

    def test_register_and_get_agent(self):
        registry = PluginRegistry()
        agent = AgentPlugin(
            name='reviewer',
            description='Code reviewer',
            system_prompt='You are a reviewer.',
        )
        registry.register_agent(agent)
        assert registry.get_agent('reviewer') is agent

    def test_command_aliases(self):
        registry = PluginRegistry()
        cmd = CommandPlugin(
            name='review',
            description='Review',
            handler=lambda: None,
            aliases=('rv', 'check'),
        )
        registry.register_command(cmd)
        assert registry.get_command('rv') is cmd
        assert registry.get_command('check') is cmd

    def test_list_commands_and_agents(self):
        registry = PluginRegistry()
        registry.register_command(CommandPlugin(name='c1', description='cmd 1', handler=lambda: None))
        registry.register_command(CommandPlugin(name='c2', description='cmd 2', handler=lambda: None))
        registry.register_agent(AgentPlugin(name='a1', description='ag 1', system_prompt='prompt'))
        assert len(registry.list_commands()) == 2
        assert len(registry.list_agents()) == 1

    def test_register_same_name_overwrites(self):
        registry = PluginRegistry()
        cmd1 = CommandPlugin(name='test', description='first', handler=lambda: 'v1')
        cmd2 = CommandPlugin(name='test', description='second', handler=lambda: 'v2')
        registry.register_command(cmd1)
        registry.register_command(cmd2)
        assert registry.get_command('test') is cmd2


class TestBuiltinPlugins:
    def test_builtin_plugins_registered(self):
        registry = PluginRegistry()
        register_builtin_plugins(registry)
        agents = registry.list_agents()
        agent_names = [a.name for a in agents]
        assert 'code-reviewer' in agent_names
        assert 'tester' in agent_names
        assert 'docs-writer' in agent_names


class TestDiscoverPlugins:
    def test_empty_directory_returns_empty(self, tmp_path):
        plugins = discover_plugins(tmp_path)
        assert plugins == []

    def test_discovers_plugin_with_manifest(self, tmp_path):
        plugin_dir = tmp_path / '.teaagent' / 'plugins' / 'my-plugin'
        plugin_dir.mkdir(parents=True)
        (plugin_dir / 'plugin.json').write_text(json.dumps({
            'name': 'my-plugin',
            'type': 'command',
            'description': 'my desc',
        }))
        plugins = discover_plugins(tmp_path)
        assert len(plugins) == 1
        assert plugins[0].manifest.name == 'my-plugin'

    def test_skips_duplicate_names(self, tmp_path):
        for sub in ('first', 'second'):
            pdir = tmp_path / '.teaagent' / 'plugins' / sub
            pdir.mkdir(parents=True)
            (pdir / 'plugin.json').write_text(json.dumps({
                'name': 'same-name',
                'type': 'command',
                'description': sub,
            }))
        plugins = discover_plugins(tmp_path)
        assert len(plugins) == 1

    def test_skips_missing_manifest(self, tmp_path):
        pdir = tmp_path / '.teaagent' / 'plugins' / 'broken'
        pdir.mkdir(parents=True)
        plugins = discover_plugins(tmp_path)
        assert plugins == []
