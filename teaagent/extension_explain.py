"""Unified extension activation explain (EXT-001).

Aggregates activation information for all extension types — MCP servers,
skills, plugins, hooks, and memories — into a single explainable structure
with source, reason, trust level, cost estimate, and disable command for
each.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Per-extension activation records ────────────────────────────────────


@dataclass
class ExtensionActivation:
    """Single extension activation record.

    Every extension type shares these fields so consumers can render a
    unified activation table.
    """

    name: str
    type: str  # "mcp" | "skill" | "plugin" | "hook" | "memory"
    source: str  # e.g. "~/.config/teaagent/skills/", "https://mcp.example.com"
    reason: str  # why it activated / loaded
    trust_level: str  # "full" | "scoped" | "untrusted" | "unknown"
    estimated_tokens: int = 0
    disable_command: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type,
            'source': self.source,
            'reason': self.reason,
            'trust_level': self.trust_level,
            'estimated_tokens': self.estimated_tokens,
            'disable_command': self.disable_command,
            'extra': self.extra,
        }


# ── Unified explain result ──────────────────────────────────────────────


@dataclass
class ExtensionActivationExplain:
    """Unified activation explain for all extension types.

    Groups activations by type and provides aggregate stats.
    """

    extensions: list[ExtensionActivation] = field(default_factory=list)
    total_count: int = 0
    total_estimated_tokens: int = 0
    trust_summary: str = ''  # e.g. "3 full, 1 scoped, 0 untrusted"

    def to_dict(self) -> dict[str, Any]:
        return {
            'extensions': [e.to_dict() for e in self.extensions],
            'total_count': self.total_count,
            'total_estimated_tokens': self.total_estimated_tokens,
            'trust_summary': self.trust_summary,
        }

    def by_type(self) -> dict[str, list[ExtensionActivation]]:
        """Group activations by their type field."""
        groups: dict[str, list[ExtensionActivation]] = {}
        for ext in self.extensions:
            groups.setdefault(ext.type, []).append(ext)
        return groups


# ── Gather functions per extension type ─────────────────────────────────


def _gather_skills(workspace_root: Optional[Path]) -> list[ExtensionActivation]:
    """Gather skill activation records."""
    if workspace_root is None:
        return []
    try:
        from teaagent.skill_loader import explain_skill_activation

        explain = explain_skill_activation(workspace_root)
        result: list[ExtensionActivation] = []

        for item in explain.loaded:
            result.append(
                ExtensionActivation(
                    name=item.name,
                    type='skill',
                    source=str(item.source_dir),
                    reason=f'Loaded (v{getattr(item, "version", 1)})',
                    trust_level='scoped',
                    estimated_tokens=item.estimated_tokens,
                    disable_command=f'teaagent skill disable {item.name}',
                )
            )

        for skipped_item in explain.skipped:
            result.append(
                ExtensionActivation(
                    name=skipped_item.skill_name,
                    type='skill',
                    source=str(skipped_item.skill_path),
                    reason=f'Skipped: {skipped_item.reason}',
                    trust_level='unknown',
                    disable_command='',
                )
            )

        return result
    except Exception:
        return []


def _gather_plugins(registry: Any = None) -> list[ExtensionActivation]:
    """Gather plugin activation records."""
    result: list[ExtensionActivation] = []
    if registry is None:
        return result
    try:
        for cmd_name in getattr(registry, 'commands', {}):
            result.append(
                ExtensionActivation(
                    name=cmd_name,
                    type='plugin',
                    source='builtin',
                    reason='Command plugin registered',
                    trust_level='full',
                    disable_command=f'plugin disable {cmd_name}',
                )
            )
        for agent_name in getattr(registry, 'agents', {}):
            result.append(
                ExtensionActivation(
                    name=agent_name,
                    type='plugin',
                    source='builtin',
                    reason='Agent plugin registered',
                    trust_level='full',
                    disable_command=f'plugin disable {agent_name}',
                )
            )
        for hook_name in getattr(registry, 'hooks', {}):
            result.append(
                ExtensionActivation(
                    name=hook_name,
                    type='plugin',
                    source='builtin',
                    reason='Hook plugin registered',
                    trust_level='full',
                    disable_command=f'plugin disable {hook_name}',
                )
            )
    except Exception:
        logger.exception('plugin gather failed')
    return result


def _gather_hooks(
    hook_registry: Any = None,
) -> list[ExtensionActivation]:
    """Gather hook activation records."""
    result: list[ExtensionActivation] = []
    if hook_registry is None:
        return result
    try:
        count = 0
        for _ in getattr(hook_registry, '_pre_hooks', []):
            count += 1
        for _ in getattr(hook_registry, '_post_hooks', []):
            count += 1
        for _ in getattr(hook_registry, '_start_hooks', []):
            count += 1
        for _ in getattr(hook_registry, '_stop_hooks', []):
            count += 1
        for _ in getattr(hook_registry, '_pre_compact_hooks', []):
            count += 1

        if count > 0:
            result.append(
                ExtensionActivation(
                    name=f'HookRegistry ({count} handlers)',
                    type='hook',
                    source='HookRegistry',
                    reason=f'{count} hook handlers registered',
                    trust_level='scoped',
                    estimated_tokens=count * 50,
                    disable_command='hook disable --all',
                )
            )
    except Exception:
        logger.exception('hook gather failed')
    return result


def _gather_mcp(
    trust_policy: Any = None,
) -> list[ExtensionActivation]:
    """Gather MCP server trust records."""
    result: list[ExtensionActivation] = []
    if trust_policy is None:
        return result
    try:
        for server_name, server_trust in getattr(trust_policy, 'servers', {}).items():
            trust_level = 'full' if server_trust.trusted else 'untrusted'
            allowed_count = len(getattr(server_trust, 'allowed_tools', []))
            denied_count = len(getattr(server_trust, 'denied_tools', []))
            result.append(
                ExtensionActivation(
                    name=server_name,
                    type='mcp',
                    source=server_name,
                    reason=(
                        f'Trusted, {allowed_count} tools allowed'
                        if server_trust.trusted
                        else f'Untrusted, {denied_count} tools denied'
                    ),
                    trust_level=trust_level,
                    disable_command=f'mcp revoke {server_name}',
                    extra={
                        'allowed_tools': allowed_count,
                        'denied_tools': denied_count,
                        'expires_at': server_trust.expires_at,
                    },
                )
            )
    except Exception:
        logger.exception('MCP gather failed')
    return result


def _gather_memories(workspace_root: Optional[Path]) -> list[ExtensionActivation]:
    """Gather memory catalog activation records."""
    if workspace_root is None:
        return []
    try:
        from teaagent.memory import MemoryCatalog

        catalog = MemoryCatalog(workspace_root, readonly=True)
        entries = catalog.list(limit=100)
        total = len(entries)

        if total == 0:
            return []

        auto_count = sum(
            1
            for e in entries
            if hasattr(e, 'kind') and getattr(e, 'kind', '') == 'auto'
        )

        return [
            ExtensionActivation(
                name=f'MemoryCatalog ({total} entries)',
                type='memory',
                source=str(workspace_root / '.teaagent' / 'memory'),
                reason=(f'{total} entries loaded ({auto_count} auto)'),
                trust_level='scoped' if auto_count > 0 else 'full',
                estimated_tokens=total * 50,
                disable_command='memory prune',
            )
        ]
    except Exception:
        return []


# ── Public API ──────────────────────────────────────────────────────────


def explain_extension_activation(
    workspace_root: Optional[str | Path] = None,
    plugin_registry: Any = None,
    hook_registry: Any = None,
    mcp_trust_policy: Any = None,
) -> ExtensionActivationExplain:
    """Build a unified activation explain for all extension types.

    Gathers activation info from:
    - Skill loader (``explain_skill_activation``)
    - Plugin registry (commands, agents, hooks registered as plugins)
    - Hook registry (pre/post/start/stop/pre_compact handlers)
    - MCP trust policy (remote servers, allowed/denied tools)
    - Memory catalog (loaded entries, auto-memory count)

    Args:
        workspace_root: Root path for workspace-scoped discovery.
        plugin_registry: Optional ``PluginRegistry`` instance.
        hook_registry: Optional ``HookRegistry`` instance.
        mcp_trust_policy: Optional ``MCPTrustPolicy`` instance.

    Returns:
        An ``ExtensionActivationExplain`` with all discovered extensions.
    """
    root_path = Path(workspace_root).resolve() if workspace_root else None

    extensions: list[ExtensionActivation] = []
    extensions.extend(_gather_skills(root_path))
    extensions.extend(_gather_plugins(plugin_registry))
    extensions.extend(_gather_hooks(hook_registry))
    extensions.extend(_gather_mcp(mcp_trust_policy))
    extensions.extend(_gather_memories(root_path))

    total_tokens = sum(e.estimated_tokens for e in extensions)
    full_count = sum(1 for e in extensions if e.trust_level == 'full')
    scoped_count = sum(1 for e in extensions if e.trust_level == 'scoped')
    untrusted_count = sum(1 for e in extensions if e.trust_level == 'untrusted')

    parts = []
    if full_count:
        parts.append(f'{full_count} full')
    if scoped_count:
        parts.append(f'{scoped_count} scoped')
    if untrusted_count:
        parts.append(f'{untrusted_count} untrusted')
    trust_summary = ', '.join(parts) if parts else 'none'

    return ExtensionActivationExplain(
        extensions=extensions,
        total_count=len(extensions),
        total_estimated_tokens=total_tokens,
        trust_summary=trust_summary,
    )
