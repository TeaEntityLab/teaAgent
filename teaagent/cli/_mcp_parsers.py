from __future__ import annotations

import argparse
from typing import Callable

from teaagent.mcp_http import DEFAULT_PORT as MCP_HTTP_DEFAULT_PORT


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    mcp = subparsers.add_parser('mcp', help='Run a local MCP-compatible server.')
    subs = mcp.add_subparsers(dest='mcp_command', required=True)

    serve = subs.add_parser(
        'serve',
        help='Serve workspace tools over stdio JSON-RPC or Streamable HTTP.',
    )
    serve.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    serve.add_argument(
        '--http',
        action='store_true',
        help='Serve over Streamable HTTP transport instead of stdio JSON-RPC.',
    )
    serve.add_argument(
        '--host',
        default='127.0.0.1',
        help='HTTP bind host. Defaults to 127.0.0.1 (loopback only).',
    )
    serve.add_argument(
        '--port',
        type=int,
        default=MCP_HTTP_DEFAULT_PORT,
        help=f'HTTP port. Defaults to {MCP_HTTP_DEFAULT_PORT}.',
    )
    serve.add_argument(
        '--auth-token',
        default=None,
        help='Require this bearer token on every HTTP request.',
    )
    serve.add_argument(
        '--allowed-origin',
        action='append',
        default=[],
        help='Permit this Origin header. Can be repeated. Default: allow all origins.',
    )
    serve.add_argument(
        '--oauth-issuer',
        default=None,
        help='Enable OAuth 2.1 / DPoP. Issuer URL (e.g. https://mcp.example.com).',
    )
    serve.add_argument(
        '--oauth-signing-key',
        default=None,
        help='HMAC signing key for JWT access tokens (min 16 chars).',
    )
    serve.add_argument(
        '--oauth-key-ring-file',
        default=None,
        help='Path to JSON key ring file: {"active_kid":"...","keys":{"kid":"secret"}}.',
    )
    serve.add_argument(
        '--oauth-active-kid',
        default=None,
        help='Override active key id (kid) from the key ring file.',
    )
    serve.add_argument(
        '--oauth-client',
        action='append',
        default=[],
        metavar='ID:SECRET:REDIRECT_URI',
        help='Pre-register an OAuth client. Format: client_id:client_secret:redirect_uri. '
        'Can be repeated.',
    )
    serve.add_argument(
        '--oauth-token-ttl',
        type=int,
        default=3600,
        help='Access token TTL in seconds. Default 3600.',
    )
    serve.add_argument(
        '--oauth-dpop-replay-ttl',
        type=int,
        default=60,
        help='DPoP proof replay-cache TTL in seconds. Default 60.',
    )
    serve.set_defaults(func=handlers['serve'])
