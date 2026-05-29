"""Control plane dashboard CLI."""

from __future__ import annotations

import argparse

from teaagent.control_plane_api import ControlPlaneServer
from teaagent.control_plane_tenant import ControlPlaneRegistry, ControlPlaneState
from teaagent.jit_approval_server import JITApprovalServer
from teaagent.tool_permissions import ToolPermissionManager


def control_plane_serve_command(args: argparse.Namespace) -> int:
    """Start the HTML control plane (workflow, focus, JIT approvals)."""
    # Callback always approves — the dashboard is the sole approval authority
    manager = ToolPermissionManager(approval_callback=lambda req: True)
    jit = JITApprovalServer(manager, timeout_seconds=args.jit_timeout_seconds)
    registry = ControlPlaneRegistry(default_tenant=args.default_tenant)
    server = ControlPlaneServer(
        host=args.host,
        port=args.port,
        tenant_registry=registry,
        jit_server=jit,
        sse_interval_seconds=args.sse_interval_seconds,
        max_sse_events=None,
    )
    server.serve_blocking()
    return 0
