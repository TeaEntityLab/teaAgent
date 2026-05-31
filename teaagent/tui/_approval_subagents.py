"""TUI helpers for centralized subagent approval batches."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    approve_request_cross_process,
    deny_request_cross_process,
    list_active_parent_run_ids,
    snapshot_pending_subagent_requests,
    try_get_approval_queue,
)


def _build_approval_tree(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a tree from a flat list using *batch_index* as nesting depth."""
    roots: list[dict[str, Any]] = []
    stack: dict[int, dict[str, Any]] = {}
    for item in items:
        raw = item.get("batch_index", None)
        depth = raw if isinstance(raw, int) and raw > 0 else 1
        node: dict[str, Any] = {"item": item, "children": []}
        if depth == 1 or not any(d < depth for d in stack):
            roots.append(node)
        else:
            parent_depth = max(d for d in stack if d < depth)
            stack[parent_depth]["children"].append(node)
        stack[depth] = node
    return roots


def _render_approval_tree(
    nodes: list[dict[str, Any]],
    lines: list[str],
    prefix: str = "",
) -> None:
    """Render tree *nodes* with Unicode box-drawing characters."""
    for idx, node in enumerate(nodes):
        is_last = idx == len(nodes) - 1
        item = node["item"]
        rid = item.get("request_id", "unknown")[:8]
        sname = item.get("subagent_name", "unknown")
        tname = item.get("tool_name", "unknown")
        batch = item.get("batch_index", "")
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}[{rid}] {sname}  {tname}  (batch {batch})")
        child_prefix = prefix + ("    " if is_last else "│   ")
        if node["children"]:
            _render_approval_tree(node["children"], lines, prefix=child_prefix)


def format_subagent_approval_batch(
    *,
    parent_run_id: Optional[str] = None,
    workspace_root: Optional[Path] = None,
) -> tuple[str, dict[str, Any]]:
    """Return human-readable summary and JSON payload for pending subagent approvals."""
    pending = snapshot_pending_subagent_requests(
        parent_run_id, workspace_root=workspace_root
    )
    parent_ids = (
        [parent_run_id] if parent_run_id else list_active_parent_run_ids(workspace_root)
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
        has_batch = any(
            isinstance(it.get('batch_index'), int) and it['batch_index'] > 0
            for it in pending
        )
        groups: dict[str, list[dict[str, Any]]] = {}
        for it in pending:
            pid = it.get('parent_run_id', 'root')
            groups.setdefault(pid, []).append(it)
        for pid, items in groups.items():
            sep_label = f'── {pid} '
            sep_width = max(40, len(sep_label) + 10)
            lines.append(f'  {sep_label}{"─" * (sep_width - len(sep_label))}')
            if not has_batch:
                for it in items:
                    rid = it.get('request_id', 'unknown')[:8]
                    sname = it.get('subagent_name', 'unknown')
                    tname = it.get('tool_name', 'unknown')
                    lines.append(f'    • [{rid}] {sname}  {tname}')
            else:
                tree = _build_approval_tree(items)
                _render_approval_tree(tree, lines, prefix='    ')
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
    explicit: Optional[str],
    *,
    fallback: Optional[str],
    workspace_root: Optional[Path] = None,
) -> Optional[str]:
    if explicit:
        return explicit
    if fallback:
        return fallback
    active = list_active_parent_run_ids(workspace_root)
    if len(active) == 1:
        return active[0]
    return None


def tui_approve_subagent_request(
    request_id: str,
    parent_run_id: str,
    *,
    workspace_root: Path,
) -> tuple[bool, str]:
    queue = try_get_approval_queue(parent_run_id, workspace_root=workspace_root)
    ok = False
    if queue is not None:
        ok = queue.approve_request_sync(request_id)
    if not ok:
        ok = approve_request_cross_process(workspace_root, parent_run_id, request_id)
    if not ok:
        return False, f"Request '{request_id}' not found or not pending"
    return True, f'approved subagent request {request_id}'


def tui_deny_subagent_request(
    request_id: str,
    parent_run_id: str,
    *,
    workspace_root: Path,
    reason: str = 'Denied by operator',
) -> tuple[bool, str]:
    queue = try_get_approval_queue(parent_run_id, workspace_root=workspace_root)
    ok = False
    if queue is not None:
        ok = queue.deny_request_sync(request_id, reason=reason)
    if not ok:
        ok = deny_request_cross_process(
            workspace_root, parent_run_id, request_id, reason=reason
        )
    if not ok:
        return False, f"Request '{request_id}' not found or not pending"
    return True, f'denied subagent request {request_id}'
