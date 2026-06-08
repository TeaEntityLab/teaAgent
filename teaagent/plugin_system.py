"""Unified Plugin System — entry-point tools + file-based manifests.

This module implements a single plugin architecture with:

**Entry-point tool plugins** (Python packaging)::

    [project.entry-points."teaagent.tools"]
    my_tools = "my_package.tools:register"

The entry-point value must be a callable with the signature::

    def register(registry: ToolRegistry) -> None: ...

**File-based manifest plugins** (JSON-driven, Claude Code compatible)::

    .teaagent/plugins/<name>/plugin.json

Four extension types: Commands, Agents, Hooks, MCP Servers.

**Unified entry point**: :func:`discover_and_load_all` loads both entry-point
tools and file-based manifests into their respective registries.

Plugin Discovery Order (first match wins for file-based):
1. Project: <workspace>/.teaagent/plugins/
2. User: ~/.config/teaagent/plugins/
3. Built-in: teaagent/plugins/builtin/

Usage::

    from teaagent.plugin_system import discover_and_load_all, PluginRegistry
    from teaagent.tools import ToolRegistry

    tool_registry = ToolRegistry()
    plugin_registry = PluginRegistry()
    result = discover_and_load_all(
        tool_registry,
        plugin_registry=plugin_registry,
        workspace_root=workspace_root,
    )
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from teaagent.tools import ToolRegistry

PLUGIN_GROUP = 'teaagent.tools'
"""Entry-point group name for third-party tool plugins."""

logger = logging.getLogger(__name__)


# ============================================================================
# Entry-point Plugin Loading (was plugins.py)
# ============================================================================


@dataclass(frozen=True)
class PluginLoadResult:
    """Summary of a plugin-loading call."""

    loaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0


def _entry_points(group: str) -> list[Any]:
    """Thin wrapper so tests can patch without touching importlib.metadata."""
    try:
        eps = importlib.metadata.entry_points()
        return list(eps.select(group=group))
    except (ImportError, AttributeError, ValueError) as exc:
        logger.warning('Failed to load entry points: %s', exc)
        return []


def _audit_plugin_source(ep: Any) -> bool:
    """Audit plugin source to warn about unverified third-party packages (RSK-10).

    Returns True if the plugin source is considered safe, False if it should be
    blocked or warned about.
    """
    try:
        # Get the module path from the entry point
        module_name = getattr(ep, 'value', None) or str(ep)
        if ':' in module_name:
            module_name = module_name.split(':')[0]

        # Try to resolve the module to its file location
        try:
            spec = importlib.util.find_spec(module_name)
            if spec and spec.origin:
                module_path = Path(spec.origin).resolve()
                # Check if module is in site-packages (third-party)
                if 'site-packages' in str(module_path):
                    from teaagent.security_env import plugins_strict_audit

                    logger.warning(
                        f'Loading plugin from third-party package: {ep.name} '
                        f'at {module_path}. Verify package source before use.'
                    )
                    return not plugins_strict_audit()
        except (ImportError, ValueError):
            pass

        from teaagent.security_env import plugins_strict_audit

        logger.warning(
            f'Unable to verify source for plugin: {ep.name}. '
            'Ensure package is from a trusted source.'
        )
        return not plugins_strict_audit()
    except (OSError, ImportError, ValueError, TypeError) as exc:
        from teaagent.security_env import plugins_strict_audit

        logger.warning('Plugin source audit failed for %s: %s', ep.name, exc)
        return not plugins_strict_audit()


def load_entry_point_tools(
    registry: ToolRegistry,
    *,
    group: str = PLUGIN_GROUP,
    _ep_loader: Any = None,
) -> PluginLoadResult:
    """Discover and load entry-point tool plugins for *group*.

    Each entry-point is loaded and called with *registry*.  Any exception
    raised during loading or registration is caught, the plugin name is
    added to :attr:`PluginLoadResult.failed`, and processing continues
    with the next plugin.

    .. note::

        This function is also available as ``load_plugins`` via
        ``from teaagent.plugins import load_plugins`` for backward
        compatibility.

    Parameters
    ----------
    registry:
        The :class:`~teaagent.tools.ToolRegistry` that plugins should
        register their tools into.
    group:
        Entry-point group name to scan (default: ``"teaagent.tools"``).

    Returns
    -------
    :class:`PluginLoadResult`
        Lists of successfully loaded and failed plugin names.
    """
    from teaagent.integration.plugin_governance import validate_plugin_tools

    loaded: list[str] = []
    failed: list[str] = []

    ep_loader = _ep_loader if _ep_loader is not None else _entry_points
    for ep in ep_loader(group):
        name = getattr(ep, 'name', str(ep))
        try:
            # Audit plugin source before loading (RSK-10)
            if not _audit_plugin_source(ep):
                logger.warning(f'Plugin {name} blocked by source audit')
                failed.append(name)
                continue

            baseline = set(registry.list_tools())
            fn = ep.load()
            fn(registry)
            added = [
                tool_name
                for tool_name in registry.list_tools()
                if tool_name not in baseline
            ]
            if added:
                report = validate_plugin_tools(registry, tool_names=added)
                if report.blocked:
                    for tool_name in added:
                        registry.unregister(tool_name)
                    logger.warning(
                        'Plugin %s blocked by tool governance: %s',
                        name,
                        report.to_dict(),
                    )
                    failed.append(name)
                    continue
            loaded.append(name)
        except Exception as exc:
            logger.warning('Plugin %s failed to load: %s', name, exc)
            failed.append(name)

    return PluginLoadResult(loaded=loaded, failed=failed)


# ============================================================================
# File-based Manifest Plugin Types
# ============================================================================


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
    """Central registry for all plugin types.

    Supports both tool registration (via an optional :class:`ToolRegistry`
    reference) and command/agent registration.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None) -> None:
        self._commands: dict[str, CommandPlugin] = {}
        self._agents: dict[str, AgentPlugin] = {}
        self._plugins: list[Plugin] = []
        self._tool_registry: Optional[ToolRegistry] = tool_registry

    # -- Tool registry access --

    @property
    def tool_registry(self) -> Optional[ToolRegistry]:
        """The associated :class:`ToolRegistry`, if any."""
        return self._tool_registry

    def set_tool_registry(self, registry: ToolRegistry) -> None:
        """Attach a :class:`ToolRegistry` to this plugin registry."""
        self._tool_registry = registry

    # -- Command / Agent registration --

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


# ============================================================================
# File-based Plugin Discovery
# ============================================================================


_DEFAULT_PLUGIN_DIRS = [
    '.teaagent/plugins',
]
_USER_PLUGIN_DIR = Path.home() / '.config' / 'teaagent' / 'plugins'
_BUILTIN_PLUGIN_DIR = Path(__file__).parent / 'plugins' / 'builtin'


def discover_plugins(root: Path) -> list[Plugin]:  # noqa: C901
    """Discover all file-based (manifest) plugins in priority order."""
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


# ============================================================================
# Built-in Plugins
# ============================================================================


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


# ============================================================================
# Unified Discovery (entry-points + file-based + builtin)
# ============================================================================


def discover_and_load_all(
    tool_registry: ToolRegistry,
    *,
    plugin_registry: Optional[PluginRegistry] = None,
    workspace_root: Optional[Path] = None,
    entry_point_group: str = PLUGIN_GROUP,
) -> PluginLoadResult:
    """Unified plugin discovery and loading.

    Loads plugins from **both** sources:

    1. **Python entry-points** (group *entry_point_group*) — calls each
       registered callable with *tool_registry* to register workspace tools.
    2. **File-based manifests** — discovers ``plugin.json`` manifests from
       ``.teaagent/plugins/`` directories and registers built-in plugins,
       populating *plugin_registry* if provided.

    Parameters
    ----------
    tool_registry:
        The :class:`~teaagent.tools.ToolRegistry` where entry-point tools
        are registered.
    plugin_registry:
        Optional :class:`PluginRegistry` for file-based manifest plugins
        and built-in plugins.
    workspace_root:
        Root directory for file-based plugin discovery.
    entry_point_group:
        Entry-point group to scan (default: ``"teaagent.tools"``).

    Returns
    -------
    :class:`PluginLoadResult`
        Summary of entry-point tool loading results.
    """
    # 1. Load entry-point tools
    result = load_entry_point_tools(tool_registry, group=entry_point_group)

    # 2. Discover file-based manifests and builtin plugins
    if plugin_registry is not None:
        register_builtin_plugins(plugin_registry)
        if workspace_root is not None:
            for plugin in discover_plugins(workspace_root):
                plugin_registry._plugins.append(plugin)

    return result
