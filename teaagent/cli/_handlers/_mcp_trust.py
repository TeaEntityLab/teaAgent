"""MCP trust policy CLI handlers."""

from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.mcp_trust import (
    load_mcp_trust_policy,
    save_mcp_trust_policy,
    update_global_tools,
    update_server_tools,
)


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def mcp_trust_list_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    _print_json({'ok': True, 'policy': policy.to_dict()})
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
    _print_json({'ok': True, 'policy': policy.to_dict()})
    return 0


def mcp_trust_allow_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    tools = list(args.tools or [])
    if args.server:
        update_server_tools(policy, args.server, allow=tools, trusted=True)
    else:
        update_global_tools(policy, allow=tools)
    save_mcp_trust_policy(args.root, policy)
    _print_json({'ok': True, 'policy': policy.to_dict()})
    return 0


def mcp_trust_deny_command(args: argparse.Namespace) -> int:
    policy = load_mcp_trust_policy(args.root)
    tools = list(args.tools or [])
    if args.server:
        update_server_tools(policy, args.server, deny=tools)
    else:
        update_global_tools(policy, deny=tools)
    save_mcp_trust_policy(args.root, policy)
    _print_json({'ok': True, 'policy': policy.to_dict()})
    return 0
