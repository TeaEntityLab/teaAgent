"""Plugin System - Four Extension Points (Claude Code compatible).

This module implements a plugin architecture with four extension types:
1. Commands - Slash commands that add CLI functionality
2. Agents - Custom subagents with specialized prompts and tools
3. Hooks - Lifecycle event handlers (already implemented in hooks.py)
4. MCP Servers - External tool integrations (already implemented)

Plugin Discovery Order (first match wins):
1. Project: <workspace>/.teaagent/plugins/
2. User: ~/.config/teaagent/plugins/
3. Built-in: teaagent/plugins/builtin/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PluginType(Enum):
    """Plugin extension types."""

    COMMAND = 'command'
    AGENT = 'agent'
    HOOK = 'hook'
    MCP_SERVER = 'mcp_server'


@dataclass(frozen=True)
class PluginManifest:
    """Plugin manifest (plugin.json)."""

    name: str
    version: str
    plugin_type: PluginType
    description: str
    author: str = 'unknown'
    license: str = 'MIT'
    entry_point: Optional[str] = None
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plugin:
    """Loaded plugin instance."""

    manifest: PluginManifest
    path: Path
    module: Any = field(default=None, repr=False)


@dataclass
class CommandPlugin:
    """Slash command plugin."""

    name: str
    description: str
    handler: Any
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class AgentPlugin:
    """Custom subagent plugin."""

    name: str
    description: str
    system_prompt: str
    tools: tuple[str, ...] = field(default_factory=tuple)
    model: Optional[str] = None


class PluginRegistry:
    """Central registry for all plugin types."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandPlugin] = {}
        self._agents: dict[str, AgentPlugin] = {}
        self._plugins: list[Plugin] = []

    def register_command(self, cmd: CommandPlugin) -> None:
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def register_agent(self, agent: AgentPlugin) -> None:
        self._agents[agent.name] = agent

    def get_command(self, name: str) -> Optional[CommandPlugin]:
        return self._commands.get(name)

    def get_agent(self, name: str) -> Optional[AgentPlugin]:
        return self._agents.get(name)

    def list_commands(self) -> list[CommandPlugin]:
        return list(self._commands.values())

    def list_agents(self) -> list[AgentPlugin]:
        return list(self._agents.values())


# --- Plugin Discovery ---


_DEFAULT_PLUGIN_DIRS = [
    '.teaagent/plugins',
]
_USER_PLUGIN_DIR = Path.home() / '.config' / 'teaagent' / 'plugins'
_BUILTIN_PLUGIN_DIR = Path(__file__).parent / 'plugins' / 'builtin'


def discover_plugins(root: Path) -> list[Plugin]:
    """Discover all plugins in priority order."""
    candidates: list[Path] = []

    for rel in _DEFAULT_PLUGIN_DIRS:
        p = root / rel
        if p.is_dir():
            candidates.append(p)

    if _USER_PLUGIN_DIR.is_dir():
        candidates.append(_USER_PLUGIN_DIR)

    if _BUILTIN_PLUGIN_DIR.is_dir():
        candidates.append(_BUILTIN_PLUGIN_DIR)

    plugins: list[Plugin] = []
    seen_names: set[str] = set()

    for plugin_dir in candidates:
        try:
            entries = sorted(plugin_dir.iterdir())
        except OSError:
            continue

        for entry in entries:
            if not entry.is_dir():
                continue

            manifest_path = entry / 'plugin.json'
            if not manifest_path.exists():
                continue

            try:
                manifest = _load_manifest(manifest_path)
            except Exception:
                continue

            if manifest.name in seen_names:
                continue

            seen_names.add(manifest.name)
            plugins.append(Plugin(manifest=manifest, path=entry))

    return plugins


def _load_manifest(path: Path) -> PluginManifest:
    """Load plugin manifest from plugin.json."""
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return PluginManifest(
        name=data['name'],
        version=data.get('version', '1.0.0'),
        plugin_type=PluginType(data['type']),
        description=data.get('description', ''),
        author=data.get('author', 'unknown'),
        license=data.get('license', 'MIT'),
        entry_point=data.get('entry_point'),
        dependencies=tuple(data.get('dependencies', [])),
        config_schema=data.get('config_schema', {}),
    )


# --- Built-in Plugins ---


def register_builtin_plugins(registry: PluginRegistry) -> None:
    """Register built-in plugins."""

    registry.register_agent(
        AgentPlugin(
            name='code-reviewer',
            description='Specialized agent for code review',
            system_prompt='You are a code review expert. Analyze code for quality, security, and best practices.',
            tools=('workspace_read_file', 'git_diff', 'grep', 'shell'),
        )
    )

    registry.register_agent(
        AgentPlugin(
            name='tester',
            description='Specialized agent for writing and running tests',
            system_prompt='You are a testing expert. Write comprehensive tests following TDD principles.',
            tools=('workspace_read_file', 'workspace_write_file', 'shell'),
        )
    )

    registry.register_agent(
        AgentPlugin(
            name='docs-writer',
            description='Specialized agent for documentation',
            system_prompt='You are a technical writer. Create clear, concise documentation.',
            tools=('workspace_read_file', 'workspace_write_file', 'grep'),
        )
    )
