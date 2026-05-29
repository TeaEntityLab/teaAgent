"""Integration tests for centralized subagent approval queue wiring."""

from __future__ import annotations

import io
import json
import threading
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.runner._types import ApprovalRequest
from teaagent.subagents._approval_queue import (
    CentralizedApprovalQueue,
    get_approval_queue,
    make_centralized_subagent_approval_handler,
    should_use_centralized_approval,
)


def test_should_use_centralized_approval_rules() -> None:
    assert not should_use_centralized_approval(parent_run_id='', batch_index=0)
    assert should_use_centralized_approval(parent_run_id='parent', batch_index=0)
    assert should_use_centralized_approval(
        parent_run_id='parent', batch_index=None, parallel_mode=True
    )
    assert not should_use_centralized_approval(
        parent_run_id='parent', batch_index=None, parallel_mode=False
    )


def test_sync_submit_and_approve() -> None:
    queue = CentralizedApprovalQueue(parent_run_id='parent-sync')
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            queue.submit_request_sync(
                subagent_id='sub-1',
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'a.py', 'content': 'x'},
                permission_mode='workspace-write',
                isolation='worktree',
                batch_index=0,
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    for _ in range(50):
        pending = queue.get_pending_requests()
        if pending:
            queue.approve_request_sync(pending[0].request_id)
            break
        thread.join(timeout=0.05)

    thread.join(timeout=2)
    assert results == [True]
    assert queue.get_pending_requests() == []


def test_centralized_handler_denied() -> None:
    queue = get_approval_queue('parent-deny')
    handler = make_centralized_subagent_approval_handler(
        parent_run_id='parent-deny',
        subagent_id='sub-1',
        subagent_name='worker',
        permission_mode='prompt',
        isolation='shared',
        batch_index=1,
    )
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            handler(
                ApprovalRequest(
                    call_id='call-1',
                    tool_name='workspace_write_file',
                    arguments={'path': 'b.py'},
                    reason='needs approval',
                    annotations={'destructive': True, 'read_only': False, 'idempotent': False},
                )
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    for _ in range(50):
        pending = queue.get_pending_requests()
        if pending:
            queue.deny_request_sync(pending[0].request_id, reason='test deny')
            break
        thread.join(timeout=0.05)

    thread.join(timeout=2)
    assert results == [False]


def test_approval_subagents_cli_list_approve() -> None:
    queue = get_approval_queue('parent-cli')
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            queue.submit_request_sync(
                subagent_id='sub-cli',
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'x.py'},
                permission_mode='workspace-write',
                isolation='worktree',
                batch_index=0,
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    request_id: str | None = None
    for _ in range(50):
        out = io.StringIO()
        with redirect_stdout(out):
            assert main(['approval', 'subagents', 'list']) == 0
        payload = json.loads(out.getvalue())
        if payload['count'] == 1:
            request_id = payload['pending'][0]['request_id']
            break
        thread.join(timeout=0.05)

    assert request_id is not None

    out = io.StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'subagents',
                    'approve',
                    request_id,
                    '--parent-run-id',
                    'parent-cli',
                ]
            )
            == 0
        )
    assert json.loads(out.getvalue())['status'] == 'approved'
    thread.join(timeout=2)
    assert results == [True]
