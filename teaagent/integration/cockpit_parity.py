"""SURF-003: shared operator cockpit snapshot for CLI, TUI, and future dashboard."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from teaagent.cockpit import assess_stale_workspace, build_control_cockpit
from teaagent.integration.approval_parity import build_pending_approvals_snapshot
from teaagent.run_store import RunStore

COCKPIT_SNAPSHOT_SCHEMA_VERSION = '1'


def build_cockpit_snapshot(
    root: str | Path,
    *,
    permission_mode: str = 'prompt',
    cost_cents: float = 0.0,
    cost_limit_cents: int | None = None,
    cost_state: str = 'unavailable',
) -> dict[str, Any]:
    """Build the shared operator cockpit payload for automation surfaces."""
    root_path = Path(root).resolve()
    store = RunStore(root_path)
    control = build_control_cockpit(
        root_path,
        permission_mode=permission_mode,
        cost_cents=cost_cents,
        cost_limit_cents=cost_limit_cents,
        cost_state=cost_state,
    )
    return {
        'schema_version': COCKPIT_SNAPSHOT_SCHEMA_VERSION,
        'control': asdict(control),
        'pending_approvals': build_pending_approvals_snapshot(store),
        'stale_workspace': assess_stale_workspace(root_path).to_dict(),
    }
