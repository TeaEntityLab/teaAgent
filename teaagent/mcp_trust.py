"""Persisted MCP tool trust policy for workspace runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.hooks import HookRegistry, mcp_tool_filter_hook
from teaagent.tools import ToolRegistry


@dataclass
class MCPServerTrust:
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    trusted: bool = False


@dataclass
class MCPTrustPolicy:
    version: int = 1
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    servers: dict[str, MCPServerTrust] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'version': self.version,
            'allowed_tools': list(self.allowed_tools),
            'denied_tools': list(self.denied_tools),
            'servers': {
                name: {
                    'allowed_tools': list(server.allowed_tools),
                    'denied_tools': list(server.denied_tools),
                    'trusted': server.trusted,
                }
                for name, server in self.servers.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'MCPTrustPolicy':
        servers: dict[str, MCPServerTrust] = {}
        raw_servers = data.get('servers')
        if isinstance(raw_servers, dict):
            for name, payload in raw_servers.items():
                if not isinstance(payload, dict):
                    continue
                servers[str(name)] = MCPServerTrust(
                    allowed_tools=[
                        str(item) for item in payload.get('allowed_tools', [])
                    ],
                    denied_tools=[
                        str(item) for item in payload.get('denied_tools', [])
                    ],
                    trusted=bool(payload.get('trusted', False)),
                )
        return cls(
            version=int(data.get('version', 1)),
            allowed_tools=[str(item) for item in data.get('allowed_tools', [])],
            denied_tools=[str(item) for item in data.get('denied_tools', [])],
            servers=servers,
        )


def trust_policy_path(root: str | Path) -> Path:
    return Path(root).resolve() / '.teaagent' / 'mcp-trust.json'


def load_mcp_trust_policy(root: str | Path) -> MCPTrustPolicy:
    path = trust_policy_path(root)
    if not path.is_file():
        return MCPTrustPolicy()
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return MCPTrustPolicy()
    if not isinstance(payload, dict):
        return MCPTrustPolicy()
    return MCPTrustPolicy.from_dict(payload)


def save_mcp_trust_policy(root: str | Path, policy: MCPTrustPolicy) -> None:
    path = trust_policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy.to_dict(), indent=2), encoding='utf-8')


def merged_tool_filters(
    policy: MCPTrustPolicy,
) -> tuple[frozenset[str], frozenset[str]]:
    allowed: set[str] = set(policy.allowed_tools)
    denied: set[str] = set(policy.denied_tools)
    for server in policy.servers.values():
        allowed.update(server.allowed_tools)
        denied.update(server.denied_tools)
    return frozenset(allowed), frozenset(denied)


def apply_mcp_trust_hooks(registry: ToolRegistry, root: str | Path) -> MCPTrustPolicy:
    """Register pre-tool hooks from persisted MCP trust policy."""
    policy = load_mcp_trust_policy(root)
    allowed, denied = merged_tool_filters(policy)
    if not allowed and not denied:
        return policy
    if registry.hook_registry is None:
        registry.hook_registry = HookRegistry()
    registry.hook_registry.register_pre_hook(
        mcp_tool_filter_hook(allowed_tools=allowed, blocked_tools=denied)
    )
    return policy


def update_global_tools(
    policy: MCPTrustPolicy,
    *,
    allow: Optional[list[str]] = None,
    deny: Optional[list[str]] = None,
) -> MCPTrustPolicy:
    if allow:
        for tool in allow:
            if tool not in policy.allowed_tools:
                policy.allowed_tools.append(tool)
            if tool in policy.denied_tools:
                policy.denied_tools.remove(tool)
    if deny:
        for tool in deny:
            if tool not in policy.denied_tools:
                policy.denied_tools.append(tool)
            if tool in policy.allowed_tools:
                policy.allowed_tools.remove(tool)
    return policy


def update_server_tools(
    policy: MCPTrustPolicy,
    server: str,
    *,
    allow: Optional[list[str]] = None,
    deny: Optional[list[str]] = None,
    trusted: Optional[bool] = None,
) -> MCPTrustPolicy:
    entry = policy.servers.setdefault(server, MCPServerTrust())
    if trusted is not None:
        entry.trusted = trusted
    if allow:
        for tool in allow:
            if tool not in entry.allowed_tools:
                entry.allowed_tools.append(tool)
            if tool in entry.denied_tools:
                entry.denied_tools.remove(tool)
    if deny:
        for tool in deny:
            if tool not in entry.denied_tools:
                entry.denied_tools.append(tool)
            if tool in entry.allowed_tools:
                entry.allowed_tools.remove(tool)
    return policy
