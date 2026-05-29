"""CLI for centralized subagent destructive-tool approval queues."""

from __future__ import annotations

import argparse

from teaagent.cli._handlers._misc import print_json
from teaagent.subagents._approval_queue import (
    list_active_parent_run_ids,
    snapshot_pending_subagent_requests,
    try_get_approval_queue,
)


def approval_subagents_list_command(args: argparse.Namespace) -> int:
    parent_run_id = getattr(args, 'parent_run_id', None)
    if parent_run_id:
        queue = try_get_approval_queue(parent_run_id)
        if queue is None:
            print_json(
                {
                    'status': 'error',
                    'message': f"No active approval queue for parent run '{parent_run_id}'",
                    'parent_run_ids': list_active_parent_run_ids(),
                }
            )
            return 1
    pending = snapshot_pending_subagent_requests(parent_run_id)
    print_json(
        {
            'parent_run_ids': list_active_parent_run_ids(),
            'pending': pending,
            'count': len(pending),
        }
    )
    return 0


def approval_subagents_approve_command(args: argparse.Namespace) -> int:
    queue = try_get_approval_queue(args.parent_run_id)
    if queue is None:
        print_json(
            {
                'status': 'error',
                'message': f"No active approval queue for parent run '{args.parent_run_id}'",
            }
        )
        return 1
    ok = queue.approve_request_sync(args.request_id)
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
    queue = try_get_approval_queue(args.parent_run_id)
    if queue is None:
        print_json(
            {
                'status': 'error',
                'message': f"No active approval queue for parent run '{args.parent_run_id}'",
            }
        )
        return 1
    reason = getattr(args, 'reason', None) or 'Denied by human'
    ok = queue.deny_request_sync(args.request_id, reason=reason)
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
    queue = try_get_approval_queue(args.parent_run_id)
    if queue is None:
        print_json(
            {
                'status': 'error',
                'message': f"No active approval queue for parent run '{args.parent_run_id}'",
            }
        )
        return 1
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
    queue = try_get_approval_queue(args.parent_run_id)
    if queue is None:
        print_json(
            {
                'status': 'error',
                'message': f"No active approval queue for parent run '{args.parent_run_id}'",
            }
        )
        return 1
    reason = getattr(args, 'reason', None) or 'Denied by human'
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
