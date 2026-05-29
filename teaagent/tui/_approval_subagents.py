"""TUI helpers for centralized subagent approval batches."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    list_active_parent_run_ids,
    snapshot_pending_subagent_requests,
    try_get_approval_queue,
)


def format_subagent_approval_batch(
    *,
    parent_run_id: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    """Return human-readable summary and JSON payload for pending subagent approvals."""
    pending = snapshot_pending_subagent_requests(parent_run_id)
    parent_ids = (
        [parent_run_id]
        if parent_run_id
        else list_active_parent_run_ids()
    )
    lines = ['Subagent approval queue']
    if parent_run_id:
        lines.append(f'  parent_run_id: {parent_run_id}')
    else:
        lines.append(f'  active_parents: {", ".join(parent_ids) or "(none)"}')
    lines.append(f'  pending_count: {len(pending)}')
    if not pending:
        lines.append('  (no pending destructive tool requests)')
    else:
        lines.append('')
        lines.append(
            f'{"#":>3}  {"request_id":<14}  {"subagent":<12}  {"tool":<28}  {"batch":>5}  {"isolation"}'
        )
        for index, item in enumerate(pending, start=1):
            lines.append(
                f'{index:>3}  {item["request_id"][:14]:<14}  '
                f'{item["subagent_name"][:12]:<12}  '
                f'{item["tool_name"][:28]:<28}  '
                f'{str(item.get("batch_index", "")):>5}  '
                f'{item.get("isolation", "")}'
            )
        lines.append('')
        lines.append(
            '  approve one:  approvals subagents approve <request_id> [--parent-run-id ID]'
        )
        lines.append(
            '  deny one:     approvals subagents deny <request_id> [--parent-run-id ID]'
        )
        lines.append(
            '  approve all:  approvals subagents approve-all [--parent-run-id ID]'
        )
        lines.append(
            '  deny all:     approvals subagents deny-all [--parent-run-id ID]'
        )
    payload: dict[str, Any] = {
        'parent_run_ids': parent_ids,
        'pending': pending,
        'count': len(pending),
    }
    if parent_run_id:
        payload['parent_run_id'] = parent_run_id
    return '\n'.join(lines), payload


def resolve_parent_run_id(
    explicit: Optional[str], *, fallback: Optional[str]
) -> Optional[str]:
    if explicit:
        return explicit
    if fallback:
        return fallback
    active = list_active_parent_run_ids()
    if len(active) == 1:
        return active[0]
    return None


def tui_approve_subagent_request(
    request_id: str, parent_run_id: str
) -> tuple[bool, str]:
    queue = try_get_approval_queue(parent_run_id)
    if queue is None:
        return False, f"No active queue for parent run '{parent_run_id}'"
    if not queue.approve_request_sync(request_id):
        return False, f"Request '{request_id}' not found or not pending"
    return True, f'approved subagent request {request_id}'


def tui_deny_subagent_request(
    request_id: str, parent_run_id: str, *, reason: str = 'Denied by operator'
) -> tuple[bool, str]:
    queue = try_get_approval_queue(parent_run_id)
    if queue is None:
        return False, f"No active queue for parent run '{parent_run_id}'"
    if not queue.deny_request_sync(request_id, reason=reason):
        return False, f"Request '{request_id}' not found or not pending"
    return True, f'denied subagent request {request_id}'
