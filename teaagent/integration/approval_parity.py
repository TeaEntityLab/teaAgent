"""SURF-009: shared pending-approval queue contract across surfaces."""

from __future__ import annotations

from typing import Any

from teaagent.approval_selectors import (
    collect_pending_approval_views,
    pending_approvals_payload,
)
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
