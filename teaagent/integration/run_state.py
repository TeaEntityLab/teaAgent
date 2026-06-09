"""Shared run-state contract for multi-surface continuity (SURF-001 / H2).

CLI, TUI, background attach, and automation surfaces query the same field names
via :meth:`teaagent.run_store.RunStore.heartbeat_for_run`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from teaagent.run_evidence import extract_git_sandbox

RUN_STATE_SCHEMA_VERSION = '1'


@dataclass(frozen=True)
class RunStateSnapshot:
    """Portable run liveness and recovery state."""

    run_id: str
    status: str
    schema_version: str = RUN_STATE_SCHEMA_VERSION
    last_heartbeat_at: str | None = None
    last_heartbeat_tick: int | None = None
    cost_cents: float = 0.0
    permission_mode: str | None = None
    undo_available: bool = False
    git_sandbox: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'run_id': self.run_id,
            'status': self.status,
            'schema_version': self.schema_version,
            'last_heartbeat_at': self.last_heartbeat_at,
            'last_heartbeat_tick': self.last_heartbeat_tick,
            'cost_cents': self.cost_cents,
            'permission_mode': self.permission_mode,
            'undo_available': self.undo_available,
        }
        if self.git_sandbox is not None:
            payload['git_sandbox'] = self.git_sandbox
        return payload


def build_run_state_snapshot(
    events: list[dict[str, Any]],
    run_id: str,
    *,
    undo_available: bool = False,
) -> RunStateSnapshot:
    """Derive the shared run-state contract from persisted audit events."""
    last_heartbeat: dict[str, Any] | None = None
    terminal_status: str | None = None
    cost_cents = 0.0
    permission_mode: str | None = None

    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            payload = {}

        if event_type == 'heartbeat':
            last_heartbeat = event
        elif event_type in {'run_completed', 'run_failed'}:
            terminal_status = (
                'completed'
                if event_type == 'run_completed'
                else f'failed:{payload.get("category", "unknown")}'
            )
            cost_cents = float(
                payload.get('cost_cents', payload.get('total_cost', 0.0)) or 0.0
            )
        elif event_type == 'run_paused':
            terminal_status = str(payload.get('status', 'paused'))
        elif event_type == 'run_started' and permission_mode is None:
            mode = payload.get('permission_mode')
            if isinstance(mode, str) and mode:
                permission_mode = mode

    git_sandbox_evidence = extract_git_sandbox(events)
    git_sandbox = (
        git_sandbox_evidence.to_dict() if git_sandbox_evidence is not None else None
    )

    tick = None
    if last_heartbeat:
        hb_payload = last_heartbeat.get('payload') or {}
        if isinstance(hb_payload, dict):
            raw_tick = hb_payload.get('tick')
            tick = int(raw_tick) if raw_tick is not None else None

    return RunStateSnapshot(
        run_id=run_id,
        status=terminal_status or 'running',
        last_heartbeat_at=last_heartbeat.get('created_at') if last_heartbeat else None,
        last_heartbeat_tick=tick,
        cost_cents=cost_cents,
        permission_mode=permission_mode,
        undo_available=undo_available,
        git_sandbox=git_sandbox,
    )
