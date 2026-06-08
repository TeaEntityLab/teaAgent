"""Control plane dashboard CLI."""

from __future__ import annotations

import argparse

from teaagent.approval import JITApprovalServer
from teaagent.control_plane_api import ControlPlaneServer
from teaagent.control_plane_tenant import ControlPlaneRegistry
from teaagent.tool_permissions import ToolPermissionManager


def control_plane_serve_command(args: argparse.Namespace) -> int:
    """Start the HTML control plane (workflow, focus, JIT approvals)."""
    # Callback always approves — the dashboard is the sole approval authority
    manager = ToolPermissionManager(approval_callback=lambda req: True)
    jit = JITApprovalServer(manager, timeout_seconds=args.jit_timeout_seconds)
    from pathlib import Path

    from teaagent.surface_auth import load_surface_auth_policy

    token_file = (
        Path(args.api_token_file) if getattr(args, 'api_token_file', None) else None
    )
    policy = load_surface_auth_policy(
        api_token=getattr(args, 'api_token', None),
        api_token_file=token_file,
        relay_mode=False,
    )
    registry = ControlPlaneRegistry(default_tenant=args.default_tenant)
    try:
        server = ControlPlaneServer(
            host=args.host,
            port=args.port,
            tenant_registry=registry,
            jit_server=jit,
            sse_interval_seconds=args.sse_interval_seconds,
            max_sse_events=None,
            auth_policy=policy,
        )
    except ValueError as exc:
        print(f'Error: {exc}')
        return 1
    server.serve_blocking()
    return 0
