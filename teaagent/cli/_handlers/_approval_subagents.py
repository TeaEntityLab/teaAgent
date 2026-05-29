"""CLI for centralized subagent destructive-tool approval queues."""

from __future__ import annotations

import argparse
from pathlib import Path

from teaagent.cli._handlers._misc import print_json
from teaagent.subagents._approval_queue import (
    approve_request_cross_process,
    deny_request_cross_process,
    get_approval_queue,
    list_active_parent_run_ids,
    snapshot_pending_subagent_requests,
    try_get_approval_queue,
)
from teaagent.subagents._approval_queue_store import ApprovalQueueStore


def _workspace_root(args: argparse.Namespace) -> Path:
    return Path(getattr(args, 'root', '.') or '.').resolve()


def approval_subagents_list_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    parent_run_id = getattr(args, 'parent_run_id', None)
    parent_ids = list_active_parent_run_ids(root)
    if parent_run_id and parent_run_id not in parent_ids:
        print_json(
            {
                'status': 'error',
                'message': f"No approval queue for parent run '{parent_run_id}'",
                'parent_run_ids': parent_ids,
            }
        )
        return 1
    pending = snapshot_pending_subagent_requests(
        parent_run_id, workspace_root=root
    )
    print_json(
        {
            'parent_run_ids': parent_ids,
            'pending': pending,
            'count': len(pending),
            'persisted': True,
        }
    )
    return 0


def approval_subagents_approve_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    queue = try_get_approval_queue(
        args.parent_run_id, workspace_root=root
    )
    ok = False
    if queue is not None:
        ok = queue.approve_request_sync(args.request_id)
    if not ok:
        ok = approve_request_cross_process(
            root, args.parent_run_id, args.request_id
        )
    if not ok:
        print_json(
            {
                'status': 'error',
                'message': f"Request '{args.request_id}' not found or not pending",
                'parent_run_id': args.parent_run_id,
            }
        )
        return 1
    print_json(
        {
            'status': 'approved',
            'request_id': args.request_id,
            'parent_run_id': args.parent_run_id,
        }
    )
    return 0


def approval_subagents_deny_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    reason = getattr(args, 'reason', None) or 'Denied by human'
    queue = try_get_approval_queue(
        args.parent_run_id, workspace_root=root
    )
    ok = False
    if queue is not None:
        ok = queue.deny_request_sync(args.request_id, reason=reason)
    if not ok:
        ok = deny_request_cross_process(
            root, args.parent_run_id, args.request_id, reason=reason
        )
    if not ok:
        print_json(
            {
                'status': 'error',
                'message': f"Request '{args.request_id}' not found or not pending",
                'parent_run_id': args.parent_run_id,
            }
        )
        return 1
    print_json(
        {
            'status': 'denied',
            'request_id': args.request_id,
            'parent_run_id': args.parent_run_id,
            'reason': reason,
        }
    )
    return 0


def approval_subagents_approve_all_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    queue = get_approval_queue(args.parent_run_id, workspace_root=root)
    queue.reload_from_store()
    count = queue.approve_all_pending_sync()
    print_json(
        {
            'status': 'approved',
            'parent_run_id': args.parent_run_id,
            'approved_count': count,
        }
    )
    return 0


def approval_subagents_deny_all_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    reason = getattr(args, 'reason', None) or 'Denied by human'
    queue = get_approval_queue(args.parent_run_id, workspace_root=root)
    queue.reload_from_store()
    count = queue.deny_all_pending_sync(reason=reason)
    print_json(
        {
            'status': 'denied',
            'parent_run_id': args.parent_run_id,
            'denied_count': count,
            'reason': reason,
        }
    )
    return 0


def approval_subagents_prune_command(args: argparse.Namespace) -> int:
    root = _workspace_root(args)
    hours = float(getattr(args, 'max_age_hours', 168) or 168)
    store = ApprovalQueueStore(root)
    report = store.prune_stale(max_age_seconds=hours * 3600.0)
    print_json(
        {
            'status': 'pruned',
            'removed_count': report.removed_count,
            'removed_parent_run_ids': report.removed_parent_run_ids,
            'skipped_pending': report.skipped_pending,
            'skipped_recent': report.skipped_recent,
            'max_age_hours': hours,
        }
    )
    return 0
