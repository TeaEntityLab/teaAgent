"""Cross-process approval queue persistence tests."""

from __future__ import annotations

import threading
from pathlib import Path

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
    approve_request_cross_process,
    get_approval_queue,
    list_active_parent_run_ids,
    try_get_approval_queue,
)
from teaagent.subagents._approval_queue_store import ApprovalQueueStore


def test_queue_persisted_and_visible_from_new_process(tmp_path: Path) -> None:
    parent_id = 'parent-persist'
    queue_a = get_approval_queue(parent_id, workspace_root=tmp_path)
    request_id = queue_a.generate_request_id()
    queue_a._requests[request_id] = SubagentApprovalRequest(
        request_id=request_id,
        subagent_id='sub-1',
        parent_run_id=parent_id,
        subagent_name='worker',
        tool_name='workspace_write_file',
        tool_arguments={'path': 'a.py'},
        permission_mode='workspace-write',
        isolation='worktree',
        batch_index=0,
        status=ApprovalRequestStatus.PENDING,
    )
    queue_a._persist()
    # Simulate separate CLI process: no in-memory registry
    from teaagent.subagents import _approval_queue as mod

    mod._approval_queues.clear()
    assert parent_id in list_active_parent_run_ids(tmp_path)
    queue_b = try_get_approval_queue(parent_id, workspace_root=tmp_path)
    assert queue_b is not None
    pending = queue_b.get_pending_requests()
    assert len(pending) == 1


def test_cross_process_approve_unblocks_waiter(tmp_path: Path) -> None:
    parent_id = 'parent-cross'
    queue = get_approval_queue(parent_id, workspace_root=tmp_path)
    results: list[bool] = []

    def waiter() -> None:
        results.append(
            queue.submit_request_sync(
                subagent_id='sub-1',
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'b.py'},
                permission_mode='workspace-write',
                isolation='worktree',
                batch_index=1,
            )
        )

    thread = threading.Thread(target=waiter)
    thread.start()

    request_id: str | None = None
    for _ in range(40):
        queue.reload_from_store()
        pending = queue.get_pending_requests()
        if pending:
            request_id = pending[0].request_id
            break
        thread.join(timeout=0.05)

    assert request_id is not None
    assert approve_request_cross_process(tmp_path, parent_id, request_id)
    thread.join(timeout=3)
    assert results == [True]


def test_prune_removes_old_resolved_queue(tmp_path: Path) -> None:
    store = ApprovalQueueStore(tmp_path)
    parent_id = 'parent-old'
    path = store.queue_path(parent_id)
    path.write_text(
        '{"parent_run_id":"parent-old","requests":{"r1":{"request_id":"r1",'
        '"subagent_id":"s","parent_run_id":"parent-old","subagent_name":"w",'
        '"tool_name":"workspace_write_file","tool_arguments":{},'
        '"permission_mode":"prompt","isolation":"worktree","status":"approved"}},'
        '"batches":{}}\n',
        encoding='utf-8',
    )
    old = path.stat().st_mtime
    import os

    os.utime(path, (old - 200000, old - 200000))
    report = store.prune_stale(max_age_seconds=3600)
    assert parent_id in report.removed_parent_run_ids
    assert not path.is_file()


def test_prune_skips_pending_queue(tmp_path: Path) -> None:
    store = ApprovalQueueStore(tmp_path)
    parent_id = 'parent-pending'
    path = store.queue_path(parent_id)
    path.write_text(
        '{"parent_run_id":"parent-pending","requests":{"r1":{"request_id":"r1",'
        '"subagent_id":"s","parent_run_id":"parent-pending","subagent_name":"w",'
        '"tool_name":"workspace_write_file","tool_arguments":{},'
        '"permission_mode":"prompt","isolation":"worktree","status":"pending"}},'
        '"batches":{}}\n',
        encoding='utf-8',
    )
    old = path.stat().st_mtime
    import os

    os.utime(path, (old - 200000, old - 200000))
    report = store.prune_stale(max_age_seconds=3600)
    assert parent_id in report.skipped_pending
    assert path.is_file()
