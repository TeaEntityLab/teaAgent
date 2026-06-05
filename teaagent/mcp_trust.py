"""Persisted MCP tool trust policy for workspace runs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from teaagent.audit import AuditLogger
from teaagent.hooks import HookError, HookRegistry
from teaagent.tools import ToolRegistry


@dataclass
class MCPServerTrust:
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    trusted: bool = False
    expires_at: Optional[float] = None  # Unix timestamp for token expiry


@dataclass
class MCPTrustPolicy:
    version: int = 1
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    servers: dict[str, MCPServerTrust] = field(default_factory=dict)
    default_ttl_seconds: float = 86400.0  # 24 hours default TTL

    def to_dict(self) -> dict[str, Any]:
        return {
            'version': self.version,
            'allowed_tools': list(self.allowed_tools),
            'denied_tools': list(self.denied_tools),
            'default_ttl_seconds': self.default_ttl_seconds,
            'servers': {
                name: {
                    'allowed_tools': list(server.allowed_tools),
                    'denied_tools': list(server.denied_tools),
                    'trusted': server.trusted,
                    'expires_at': server.expires_at,
                }
                for name, server in self.servers.items()
            },
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            'version': self.version,
            'allowed_tools': list(self.allowed_tools),
            'denied_tools': list(self.denied_tools),
            'default_ttl_seconds': self.default_ttl_seconds,
            'servers': {
                name: {
                    'allowed_tools': list(server.allowed_tools),
                    'denied_tools': list(server.denied_tools),
                    'expires_at': server.expires_at,
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
                    expires_at=payload.get('expires_at'),
                )
        return cls(
            version=int(data.get('version', 1)),
            allowed_tools=[str(item) for item in data.get('allowed_tools', [])],
            denied_tools=[str(item) for item in data.get('denied_tools', [])],
            servers=servers,
            default_ttl_seconds=float(data.get('default_ttl_seconds', 86400.0)),
        )


def trust_policy_path(root: str | Path) -> Path:
    return Path(root).resolve() / '.teaagent' / 'mcp-trust.json'


def _get_trust_policy_fernet() -> Fernet:
    """Get Fernet instance for MCP trust policy encryption with validation."""
    if 'TEAAGENT_MCP_TRUST_KEY' not in os.environ:
        raise ValueError(
            'TEAAGENT_MCP_TRUST_KEY environment variable is required for MCP trust policy encryption. '
            'Generate a valid key using: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
        )

    key = os.environ['TEAAGENT_MCP_TRUST_KEY']

    # Validate key format - Fernet keys must be 32 bytes, base64-encoded
    try:
        key_bytes = key.encode('utf-8')
        # Validate by attempting to create Fernet instance
        fernet = Fernet(key_bytes)
    except Exception as e:
        raise ValueError(
            f'Invalid TEAAGENT_MCP_TRUST_KEY format: {e}. '
            'The key must be a valid Fernet key (32 bytes, base64-encoded). '
            'Generate a valid key using: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
        ) from e

    return fernet


def _serialize_policy(policy: MCPTrustPolicy) -> str:
    fernet = _get_trust_policy_fernet()
    plaintext = json.dumps(policy.to_dict(), indent=2).encode('utf-8')
    return fernet.encrypt(plaintext).decode('utf-8')


def _deserialize_policy(raw_text: str) -> dict[str, Any]:
    fernet = _get_trust_policy_fernet()
    plaintext = fernet.decrypt(raw_text.encode('utf-8'))
    payload = json.loads(plaintext.decode('utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('Invalid trust policy payload')
    return payload


def load_mcp_trust_policy(root: str | Path) -> MCPTrustPolicy:
    path = trust_policy_path(root)
    if not path.is_file():
        return MCPTrustPolicy()
    try:
        raw_text = path.read_text(encoding='utf-8')
        payload = _deserialize_policy(raw_text)
    except (OSError, json.JSONDecodeError, InvalidToken, KeyError, ValueError):
        return MCPTrustPolicy()
    return MCPTrustPolicy.from_dict(payload)


def save_mcp_trust_policy(root: str | Path, policy: MCPTrustPolicy) -> None:
    path = trust_policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted_payload = _serialize_policy(policy)
    path.write_text(encrypted_payload, encoding='utf-8')


def merged_tool_filters(
    policy: MCPTrustPolicy,
) -> tuple[frozenset[str], frozenset[str]]:
    allowed: set[str] = set(policy.allowed_tools)
    denied: set[str] = set(policy.denied_tools)
    for server in policy.servers.values():
        if is_server_trust_expired(server):
            continue
        allowed.update(server.allowed_tools)
        denied.update(server.denied_tools)
    return frozenset(allowed), frozenset(denied)


def apply_mcp_trust_hooks(registry: ToolRegistry, root: str | Path) -> MCPTrustPolicy:
    """Register pre-tool hooks from persisted MCP trust policy."""
    policy = load_mcp_trust_policy(root)
    if registry.hook_registry is None:
        registry.hook_registry = HookRegistry()

    def dynamic_mcp_trust_hook(
        tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | None:
        current_policy = load_mcp_trust_policy(root)

        # P2-A-001: Enforce trust expiry at call time for every server,
        # regardless of whether the tool appears in allow/deny lists.
        for server_name, server in current_policy.servers.items():
            if not server.trusted:
                raise HookError(f"MCP server '{server_name}' is not trusted")
            if is_server_trust_expired(server):
                raise HookError(
                    f"Trust for MCP server '{server_name}' has expired "
                    f'(expired at {server.expires_at})'
                )

        allowed, denied = merged_tool_filters(current_policy)
        if denied and tool_name in denied:
            raise HookError(f"MCP tool '{tool_name}' is blocked")
        if allowed and tool_name not in allowed:
            raise HookError(
                f"MCP tool '{tool_name}' not in allowed list. "
                f'Allowed: {sorted(allowed)}'
            )
        return None

    registry.hook_registry.register_pre_hook(dynamic_mcp_trust_hook)
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
    ttl_seconds: Optional[float] = None,
) -> MCPTrustPolicy:
    """Update server trust with optional TTL for token expiry."""
    entry = policy.servers.setdefault(server, MCPServerTrust())
    if trusted is not None:
        entry.trusted = trusted
        # Set expiry when trusting a server
        if trusted and ttl_seconds is None:
            ttl_seconds = policy.default_ttl_seconds
        if trusted and ttl_seconds is not None:
            entry.expires_at = time.time() + ttl_seconds
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


def is_server_trust_expired(server_trust: MCPServerTrust) -> bool:
    """Check if server trust has expired based on expires_at timestamp."""
    if server_trust.expires_at is None:
        return False
    return time.time() > server_trust.expires_at


def revoke_server_trust(
    policy: MCPTrustPolicy,
    server: str,
    *,
    audit_logger: Optional[AuditLogger] = None,
    run_id: Optional[str] = None,
) -> MCPTrustPolicy:
    """Revoke trust for a server and emit audit event."""
    if server in policy.servers:
        entry = policy.servers[server]
        # Emit audit event
        if audit_logger is not None:
            audit_logger.record(
                event_type='mcp_server_trust_revoked',
                run_id=run_id or 'unknown',
                server=server,
                previous_trusted=entry.trusted,
                previous_allowed_tools=len(entry.allowed_tools),
                previous_denied_tools=len(entry.denied_tools),
            )
        # Remove server entry
        del policy.servers[server]
    return policy


def check_mcp_server_trust_at_call_time(
    root: str | Path,
    tool_name: str,
    server_name: str,
) -> None:
    """Enforce MCP trust expiry at call time — rejects expired trust entries.

    This is the call-time guard that MUST be invoked before executing any
    MCP tool.  It inspects the persisted trust policy and raises
    ``HookError`` when the server's trust window has elapsed, regardless
    of whether the tool appears in allow/deny lists.

    Raises:
        HookError: If the server trust has expired or the server is not trusted.
    """
    policy = load_mcp_trust_policy(root)
    server = policy.servers.get(server_name)
    if server is None:
        # Unknown server — let the existing tool-filter hook decide.
        return
    if not server.trusted:
        raise HookError(
            f"MCP server '{server_name}' is not trusted. "
            f"Use 'teaagent mcp-trust trust --server {server_name}' to grant trust."
        )
    if is_server_trust_expired(server):
        raise HookError(
            f"Trust for MCP server '{server_name}' has expired "
            f'(expired at {server.expires_at}). '
            f"Use 'teaagent mcp-trust trust --server {server_name}' to renew."
        )


def is_docker_available() -> bool:
    """Check whether Docker is installed and reachable."""
    import subprocess

    result = subprocess.run(
        ['docker', '--version'],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_unknown_tool_prompt(
    policy: MCPTrustPolicy,
    tool_name: str,
    server: Optional[str] = None,
) -> bool:
    """Check if an unknown tool should trigger a default-deny prompt.

    Returns True if the tool is unknown and should trigger a prompt.
    """
    # Check global allow/deny lists
    if tool_name in policy.allowed_tools:
        return False
    if tool_name in policy.denied_tools:
        return False

    # Check server-specific lists if server is provided
    if server and server in policy.servers:
        server_trust = policy.servers[server]
        if tool_name in server_trust.allowed_tools:
            return False
        if tool_name in server_trust.denied_tools:
            return False

    # Tool is unknown - should trigger default-deny prompt
    return True
