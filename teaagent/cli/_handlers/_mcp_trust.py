"""MCP trust policy CLI handlers."""

from __future__ import annotations

import argparse
from typing import Any

from teaagent.cli._output import _redact_value
from teaagent.mcp_trust import (
    load_mcp_trust_policy,
    revoke_server_trust,
    save_mcp_trust_policy,
    update_global_tools,
    update_server_tools,
)
from teaagent.run_store import RunStore


def _strip_sensitive_fields(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.strip().lower() == 'trusted':
                continue
            sanitized[key] = _strip_sensitive_fields(item)
        return sanitized
    if isinstance(value, list):
        return [_strip_sensitive_fields(item) for item in value]
    return value


def _redact_sensitive(value: Any) -> Any:
    def _is_sensitive_key(key: Any) -> bool:
        if not isinstance(key, str):
            return False
        normalized = key.strip().lower()
        if normalized in {'trusted', 'trust', 'secret', 'token', 'password', 'key'}:
            return True
        return (
            'trusted' in normalized
            or 'secret' in normalized
            or 'token' in normalized
            or 'password' in normalized
            or normalized.endswith('_key')
        )

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                redacted[key] = '[REDACTED]'
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _print_json(value: Any) -> None:
    from teaagent.cli._output import print_json

    sanitized = _redact_value(_redact_sensitive(_strip_sensitive_fields(value)))
    print_json(sanitized)


def mcp_trust_list_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    _print_json({'ok': True, 'policy': policy.to_public_dict()})
    return 0


def mcp_trust_inspect_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    server = getattr(args, 'server', None)
    if server:
        entry = policy.servers.get(server)
        if entry is None:
            _print_json({'ok': False, 'error': f"server '{server}' not found"})
            return 1
        _print_json(
            {
                'ok': True,
                'server': server,
                'allowed_tools': entry.allowed_tools,
                'denied_tools': entry.denied_tools,
                'trusted': entry.trusted,
            }
        )
        return 0
    _print_json({'ok': True, 'policy': policy.to_public_dict()})
    return 0


def mcp_trust_allow_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    tools = list(args.tools or [])
    if args.server:
        update_server_tools(policy, args.server, allow=tools, trusted=True)
    else:
        update_global_tools(policy, allow=tools)
    save_mcp_trust_policy(args.root, policy)
    _print_json({'ok': True, 'policy': policy.to_public_dict()})
    return 0


def mcp_trust_deny_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    tools = list(args.tools or [])
    if args.server:
        update_server_tools(policy, args.server, deny=tools)
    else:
        update_global_tools(policy, deny=tools)
    save_mcp_trust_policy(args.root, policy)
    _print_json({'ok': True, 'policy': policy.to_public_dict()})
    return 0


def mcp_trust_revoke_command(args: argparse.Namespace) -> int:
    """Revoke trust for an MCP server (removes it from the trust policy)."""
    policy = load_mcp_trust_policy(args.root)
    server = args.server
    if server not in policy.servers:
        _print_json({'ok': False, 'error': f"server '{server}' not found"})
        return 1
    policy = revoke_server_trust(policy, server)
    save_mcp_trust_policy(args.root, policy)
    _print_json({'ok': True, 'revoked': server, 'policy': policy.to_public_dict()})
    return 0


def mcp_trust_audit_command(args: argparse.Namespace) -> int:
    """Show MCP trust audit trail from run audit logs."""
    try:
        store = RunStore(args.root, readonly=True)
        runs = store.list_runs(limit=20)
        events: list[dict[str, Any]] = []
        for run in runs:
            try:
                run_events = store.show_run(run.run_id)
                for ev in run_events:
                    if not isinstance(ev, dict):
                        continue
                    event_type = ev.get('event_type', '')
                    if 'mcp_server_trust' in event_type or 'mcp_trust' in event_type:
                        entry: dict[str, Any] = {
                            'run_id': run.run_id[:12],
                            'event_type': event_type,
                            'timestamp': ev.get('timestamp'),
                        }
                        payload = ev.get('payload') or {}
                        if isinstance(payload, dict):
                            entry['server'] = payload.get('server', '')
                            if args.server and args.server not in str(
                                entry.get('server', '')
                            ):
                                continue
                            entry['details'] = {
                                k: v
                                for k, v in payload.items()
                                if k != 'password' and 'secret' not in k
                            }
                        events.append(entry)
            except (FileNotFoundError, OSError):
                continue
        _print_json({'ok': True, 'events': events})
        return 0
    except Exception as exc:
        _print_json({'ok': False, 'error': str(exc)})
        return 1
