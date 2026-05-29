"""Publish swarm and workflow snapshots to the control plane dashboard."""

from __future__ import annotations

from typing import Any

from teaagent.control_plane_api import ControlPlaneState


def publish_swarm_workflow(
    state: ControlPlaneState,
    *,
    parent_run_id: str,
    phase: str,
    subagents: list[dict[str, Any]],
    totals: dict[str, Any] | None = None,
) -> None:
    """Update workflow and focus snapshots for dashboard SSE consumers."""
    payload: dict[str, Any] = {
        'parent_run_id': parent_run_id,
        'phase': phase,
        'subagents': subagents,
    }
    if totals:
        payload['totals'] = totals
    state.set_workflow(payload)
    focus_task = next(
        (item for item in subagents if item.get('status') == 'running'),
        subagents[0] if subagents else None,
    )
    state.set_focus(
        {
            'parent_run_id': parent_run_id,
            'phase': phase,
            'active_task': focus_task,
        }
    )
