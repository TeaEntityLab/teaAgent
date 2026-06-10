"""WDE-001 remote approval backend cross-process grant."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.coordination.approval_backend import (
    RemoteApprovalCoordinationBackend,
    resolve_approval_backend,
)
from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
    get_approval_queue,
)


def test_remote_file_backend_second_process_grants(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        url = f'file://{root}'
        monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', 'remote')
        monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_URL', url)

        parent_id = 'parent-remote'
        queue = get_approval_queue(parent_id, workspace_root=root)
        request_id = queue.generate_request_id()
        queue._requests[request_id] = SubagentApprovalRequest(  # noqa: SLF001
            request_id=request_id,
            subagent_id='sub-1',
            parent_run_id=parent_id,
            subagent_name='worker',
            tool_name='workspace_write_file',
            tool_arguments={'path': 'a.py'},
            permission_mode='workspace-write',
            isolation='worktree',
            status=ApprovalRequestStatus.PENDING,
        )
        queue._persist(force=True)  # noqa: SLF001

        remote = resolve_approval_backend(root)
        assert isinstance(remote, RemoteApprovalCoordinationBackend)
        ok = remote.update_request_status(
            parent_id,
            request_id,
            ApprovalRequestStatus.APPROVED,
            approved_by='second-process',
        )
        assert ok is True
        snapshot = remote.load_snapshot(parent_id)
        assert snapshot.requests[request_id]['status'] == 'approved'
