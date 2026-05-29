"""Control plane CLI argument parsers."""

from __future__ import annotations

import argparse
from typing import Any


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Any],
) -> None:
    plane_parser = subparsers.add_parser(
        'control-plane', help='Workflow/focus/JIT dashboard server'
    )
    plane_subs = plane_parser.add_subparsers(
        dest='control_plane_command', required=True
    )
    serve_cmd = plane_subs.add_parser(
        'serve', help='Start the local control plane dashboard'
    )
    serve_cmd.add_argument(
        '--host',
        default='127.0.0.1',
        help='Bind host. Defaults to 127.0.0.1.',
    )
    serve_cmd.add_argument(
        '--port',
        type=int,
        default=8765,
        help='Bind port. Default 8765.',
    )
    serve_cmd.add_argument(
        '--jit-timeout-seconds',
        type=int,
        default=300,
        help='JIT approval request timeout. Default 300.',
    )
    serve_cmd.add_argument(
        '--sse-interval-seconds',
        type=float,
        default=1.0,
        help='SSE poll interval for dashboard streams. Default 1.0.',
    )
    serve_cmd.add_argument(
        '--default-tenant',
        default='default',
        help='Default tenant when X-TeaAgent-Tenant header is omitted.',
    )
    serve_cmd.add_argument(
        '--api-token',
        help='Bearer token (admin scope) for dashboard/API access',
    )
    serve_cmd.add_argument(
        '--api-token-file',
        help='JSON token file mapping tokens to allowed tenants',
    )
    serve_cmd.set_defaults(func=handlers.get('serve'))
