"""SURF-009: shared pending-approval queue contract across surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaagent.approval_selectors import (
    collect_pending_approval_views,
    pending_approvals_payload,
)
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.run_store import RunStore

APPROVAL_QUEUE_SCHEMA_VERSION = '1'


def build_pending_approvals_snapshot(
    store: RunStore,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Build the shared pending-approval queue payload for CLI, TUI, and IDE."""
    views = collect_pending_approval_views(store, limit=limit)
    return {
        'schema_version': APPROVAL_QUEUE_SCHEMA_VERSION,
        **pending_approvals_payload(views),
    }


def find_pending_approval_for_call_id(
    store: RunStore,
    call_id: str,
    *,
    limit: int = 100,
) -> tuple[str, dict[str, Any]] | None:
    """Return ``(run_id, pending_payload)`` when *call_id* is queued."""
    for summary in store.list_runs(limit=limit):
        pending = store.pending_approval_for_run(summary.run_id)
        if pending and pending.get('call_id') == call_id:
            return summary.run_id, pending
    return None


def grant_pending_approval(
    root: str | Path,
    call_id: str,
    *,
    limit: int = 100,
) -> dict[str, Any] | None:
    """Persist scoped approval for a pending call. Returns grant metadata or None."""
    approval_store = ApprovalPresetStore(root)
    store = RunStore(root)
    found = find_pending_approval_for_call_id(store, call_id, limit=limit)
    if not found:
        return None
    run_id, pending = found
    raw_arguments = pending.get('arguments')
    if isinstance(raw_arguments, dict):
        arguments = {str(key): value for key, value in raw_arguments.items()}
    else:
        arguments = {}
    digest = pending.get('argument_digest')
    approval_store.add_scoped_approval(
        run_id=run_id,
        call_id=call_id,
        tool_name=str(pending.get('tool_name', 'unknown')),
        arguments=arguments,
        argument_digest=digest if isinstance(digest, str) and digest else None,
    )
    return {
        'run_id': run_id,
        'call_id': call_id,
        'tool_name': pending.get('tool_name', 'unknown'),
    }


def build_approval_granted_payload(grant: dict[str, Any]) -> dict[str, Any]:
    """CLI/TUI payload after approve-without-resume."""
    return {
        'status': 'approved',
        'call_id': grant['call_id'],
        'run_id': grant['run_id'],
        'note': 'Use --resume to continue the run',
    }
