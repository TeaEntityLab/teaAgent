from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from teaagent.cli._handlers._agent.config import _parse_approve_scoped
from teaagent.mcp_http import is_loopback_host
from teaagent.mcp_server import MCPGovernance, serve_mcp_stdio
from teaagent.oauth21 import OAuth21AuthorizationServer, OAuthKeyRing
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.workspace_tools import build_workspace_tool_registry


def mcp_serve_command(args: argparse.Namespace) -> int:
    if args.permission_mode == PermissionMode.WORKSPACE_WRITE.value:
        # workspace-write lets file writes through on the strength of a bound
        # plan (PLAN_GATE on `run`); MCP clients bind no plan, so the mode would
        # silently become "write anything". Fail closed instead.
        print(
            'mcp serve does not support --permission-mode workspace-write: it relies '
            'on a bound plan, which MCP clients cannot provide. Use prompt (with '
            '`teaagent approval grant` presets or --approve-scoped), read-only, or allow.',
            file=sys.stderr,
        )
        return 2
    registry = build_workspace_tool_registry(args.root)
    if args.http:
        oauth_server = None
        key_ring = None
        if args.oauth_key_ring_file:
            key_ring, error = _load_key_ring(
                Path(args.oauth_key_ring_file),
                active_kid_override=args.oauth_active_kid,
                rotation_window_seconds=args.oauth_rotation_window,
            )
            if error:
                print('Invalid OAuth key ring configuration.', file=sys.stderr)
                return 1
        elif args.oauth_active_kid:
            print(
                '--oauth-active-kid requires --oauth-key-ring-file.',
                file=sys.stderr,
            )
            return 1
        if args.oauth_issuer and args.oauth_signing_key:
            oauth_server = OAuth21AuthorizationServer(
                signing_key=args.oauth_signing_key,
                issuer=args.oauth_issuer,
                token_ttl=args.oauth_token_ttl,
                refresh_token_ttl=args.oauth_refresh_token_ttl,
                dpop_replay_ttl=args.oauth_dpop_replay_ttl,
                key_ring=key_ring,
            )
            for spec in args.oauth_client or []:
                parts = spec.split(':', 2)
                if len(parts) != 3:
                    print(
                        'Invalid --oauth-client format (expected ID:SECRET:REDIRECT_URI).',
                        file=sys.stderr,
                    )
                    return 1
                oauth_server.register_client(*parts)
        elif args.oauth_issuer or args.oauth_signing_key:
            print(
                'Both --oauth-issuer and --oauth-signing-key must be provided to enable OAuth.',
                file=sys.stderr,
            )
            return 1
        if (
            not is_loopback_host(args.host)
            and not args.auth_token
            and oauth_server is None
        ):
            print(
                'Refusing to serve MCP HTTP on a non-loopback host without --auth-token or OAuth.',
                file=sys.stderr,
            )
            return 1
        governance = _open_governance(args, transport='http')
        try:
            return args._serve_mcp_http(
                registry,
                governance=governance,
                host=args.host,
                port=args.port,
                auth_token=args.auth_token,
                allowed_origins=args.allowed_origin or None,
                oauth_server=oauth_server,
            )
        finally:
            governance.close()
    governance = _open_governance(args, transport='stdio')
    try:
        return serve_mcp_stdio(registry, governance=governance)
    finally:
        governance.close()


def _open_governance(args: argparse.Namespace, *, transport: str) -> MCPGovernance:
    """Bind the server to the workspace approval policy and a run log."""
    return MCPGovernance.for_workspace(
        args.root,
        permission_mode=parse_permission_mode(args.permission_mode),
        transport=transport,
        approved_payload_digests=_parse_approve_scoped(args.approve_scoped),
    )


def _load_key_ring(
    path: Path, *, active_kid_override: str | None, rotation_window_seconds: int = 0
) -> tuple[OAuthKeyRing | None, str | None]:
    if not path.exists():
        return None, 'OAuth key ring file not found.'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None, 'Failed to read OAuth key ring file.'
    if not isinstance(payload, dict):
        return None, 'OAuth key ring file must contain a JSON object.'
    raw_keys = payload.get('keys')
    if not isinstance(raw_keys, dict) or not raw_keys:
        return None, "OAuth key ring file requires non-empty 'keys' object."

    keys: dict[str, bytes] = {}
    for kid, secret in raw_keys.items():
        if not isinstance(kid, str) or not kid:
            return None, 'OAuth key ring keys must use non-empty string kids.'
        if not isinstance(secret, str) or len(secret) < 16:
            return (
                None,
                'OAuth key ring secrets must be strings with length >= 16 chars.',
            )
        keys[kid] = secret.encode('utf-8')

    active_kid = active_kid_override or payload.get('active_kid')
    if not isinstance(active_kid, str) or not active_kid:
        return (
            None,
            "OAuth key ring file requires string 'active_kid' or --oauth-active-kid.",
        )
    if active_kid not in keys:
        return (
            None,
            'OAuth key ring validation failed: active_kid is not present in keys.',
        )

    return OAuthKeyRing(
        active_kid=active_kid,
        keys=keys,
        rotation_window_seconds=rotation_window_seconds,
    ), None
