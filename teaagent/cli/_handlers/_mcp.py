from __future__ import annotations

import argparse
import sys

from teaagent.mcp_http import is_loopback_host
from teaagent.mcp_server import serve_mcp_stdio
from teaagent.workspace_tools import build_workspace_tool_registry


def mcp_serve_command(args: argparse.Namespace) -> int:
    from teaagent.oauth21 import OAuth21AuthorizationServer

    registry = build_workspace_tool_registry(args.root)
    if args.http:
        oauth_server = None
        if args.oauth_issuer and args.oauth_signing_key:
            oauth_server = OAuth21AuthorizationServer(
                signing_key=args.oauth_signing_key,
                issuer=args.oauth_issuer,
                token_ttl=args.oauth_token_ttl,
            )
            for spec in args.oauth_client or []:
                parts = spec.split(':', 2)
                if len(parts) != 3:
                    print(
                        f'Invalid --oauth-client format: {spec} (expected ID:SECRET:REDIRECT_URI)',
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
        return args._serve_mcp_http(  # type: ignore[attr-defined]
            registry,
            host=args.host,
            port=args.port,
            auth_token=args.auth_token,
            allowed_origins=args.allowed_origin or None,
            oauth_server=oauth_server,
        )
    return serve_mcp_stdio(registry)
