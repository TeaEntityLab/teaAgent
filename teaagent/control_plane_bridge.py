"""Publish swarm and workflow snapshots to the control plane dashboard."""

from __future__ import annotations

from typing import Any

from teaagent.control_plane_tenant import (
    ControlPlaneRegistry,
    ControlPlaneState,
)


def publish_swarm_workflow(
    state: ControlPlaneState | ControlPlaneRegistry,
    *,
    parent_run_id: str,
    phase: str,
    subagents: list[dict[str, Any]],
    totals: dict[str, Any] | None = None,
    tenant_id: str = 'default',
) -> None:
    """Update workflow and focus snapshots for dashboard SSE consumers."""
    if isinstance(state, ControlPlaneRegistry):
        target = state.get_or_create(tenant_id)
    else:
        target = state
    payload: dict[str, Any] = {
        'parent_run_id': parent_run_id,
        'phase': phase,
        'subagents': subagents,
        'tenant_id': tenant_id,
    }
    if totals:
        payload['totals'] = totals
    target.set_workflow(payload)
    focus_task = next(
        (item for item in subagents if item.get('status') == 'running'),
        subagents[0] if subagents else None,
    )
    target.set_focus(
        {
            'parent_run_id': parent_run_id,
            'phase': phase,
            'active_task': focus_task,
            'tenant_id': tenant_id,
        }
    )
