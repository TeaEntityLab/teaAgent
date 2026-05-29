"""Control plane dashboard CLI."""

from __future__ import annotations

import argparse

from teaagent.control_plane_api import ControlPlaneServer, ControlPlaneState
from teaagent.jit_approval_server import JITApprovalServer
from teaagent.tool_permissions import ToolPermissionManager


def control_plane_serve_command(args: argparse.Namespace) -> int:
    """Start the HTML control plane (workflow, focus, JIT approvals)."""
    # Callback always approves — the dashboard is the sole approval authority
    manager = ToolPermissionManager(approval_callback=lambda req: True)
    jit = JITApprovalServer(manager, timeout_seconds=args.jit_timeout_seconds)
    state = ControlPlaneState()
    server = ControlPlaneServer(
        host=args.host,
        port=args.port,
        state=state,
        jit_server=jit,
        sse_interval_seconds=args.sse_interval_seconds,
        max_sse_events=None,
    )
    server.serve_blocking()
    return 0
