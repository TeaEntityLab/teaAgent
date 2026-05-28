"""Plugin CLI handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.plugin_system import (
    PluginRegistry,
    discover_plugins,
    register_builtin_plugins,
)


def plugin_list_command(args: argparse.Namespace) -> int:
    """List all discovered plugins."""
    root = Path(args.root).resolve()
    registry = PluginRegistry()
    register_builtin_plugins(registry)

    plugins = discover_plugins(root)

    if not plugins:
        print('No plugins discovered.')
        return 0

    print(f'Discovered {len(plugins)} plugin(s):\n')

    for plugin in plugins:
        print(f'  Name: {plugin.manifest.name}')
        print(f'  Version: {plugin.manifest.version}')
        print(f'  Type: {plugin.manifest.plugin_type.value}')
        print(f'  Description: {plugin.manifest.description}')
        print(f'  Author: {plugin.manifest.author}')
        print(f'  Path: {plugin.path}')
        if plugin.manifest.entry_point:
            print(f'  Entry Point: {plugin.manifest.entry_point}')
        if plugin.manifest.dependencies:
            print(f'  Dependencies: {", ".join(plugin.manifest.dependencies)}')
        print()

    # List registered commands and agents
    commands = registry.list_commands()
    agents = registry.list_agents()

    if commands:
        print(f'Registered Commands ({len(commands)}):')
        for cmd in commands:
            print(f'  - {cmd.name}: {cmd.description}')
            if cmd.aliases:
                print(f'    Aliases: {", ".join(cmd.aliases)}')
        print()

    if agents:
        print(f'Registered Agents ({len(agents)}):')
        for agent in agents:
            print(f'  - {agent.name}: {agent.description}')
            if agent.tools:
                print(f'    Tools: {", ".join(agent.tools)}')
        print()

    return 0


def plugin_show_command(args: argparse.Namespace) -> int:
    """Show detailed information about a specific plugin."""
    root = Path(args.root).resolve()
    plugins = discover_plugins(root)

    plugin = None
    for p in plugins:
        if p.manifest.name == args.name:
            plugin = p
            break

    if plugin is None:
        print(f"Plugin '{args.name}' not found.")
        return 1

    print(f'Plugin: {plugin.manifest.name}')
    print(f'Version: {plugin.manifest.version}')
    print(f'Type: {plugin.manifest.plugin_type.value}')
    print(f'Description: {plugin.manifest.description}')
    print(f'Author: {plugin.manifest.author}')
    print(f'License: {plugin.manifest.license}')
    print(f'Path: {plugin.path}')

    if plugin.manifest.entry_point:
        print(f'Entry Point: {plugin.manifest.entry_point}')

    if plugin.manifest.dependencies:
        print('Dependencies:')
        for dep in plugin.manifest.dependencies:
            print(f'  - {dep}')

    if plugin.manifest.config_schema:
        print('Config Schema:')
        print(json.dumps(plugin.manifest.config_schema, indent=2))

    return 0


def plugin_verify_command(args: argparse.Namespace) -> int:
    """Verify plugin manifest and entry point."""
    root = Path(args.root).resolve()
    plugins = discover_plugins(root)

    plugin = None
    for p in plugins:
        if p.manifest.name == args.name:
            plugin = p
            break

    if plugin is None:
        print(f"Plugin '{args.name}' not found.")
        return 1

    print(f'Verifying plugin: {plugin.manifest.name}')

    # Check manifest
    manifest_path = plugin.path / 'plugin.json'
    if not manifest_path.exists():
        print(f'  [FAIL] plugin.json not found at {manifest_path}')
        return 1

    print('  [OK] plugin.json found')

    # Check entry point if specified
    if plugin.manifest.entry_point:
        try:
            module_path, func_name = plugin.manifest.entry_point.split(':')
            print(f'  [OK] Entry point format valid: {module_path}:{func_name}')
        except ValueError:
            print(f'  [FAIL] Invalid entry point format: {plugin.manifest.entry_point}')
            return 1

    print('  [OK] Plugin verification passed')
    return 0
