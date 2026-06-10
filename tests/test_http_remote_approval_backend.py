"""HTTP remote approval backend integration (WDE-001)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.coordination.approval_backend import (
    FileBackedApprovalBackend,
    RemoteApprovalCoordinationBackend,
    resolve_approval_backend,
)
from teaagent.coordination.approval_http_server import ApprovalCoordinationHttpServer
from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
    get_approval_queue,
)


def test_http_remote_backend_second_client_grants() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        file_backend = FileBackedApprovalBackend(root)
        server = ApprovalCoordinationHttpServer(
            file_backend,
            host='127.0.0.1',
            port=0,
            auth_token='secret-token',
        )
        server.start()
        try:
            remote = RemoteApprovalCoordinationBackend(
                server.base_url,
                auth_token='secret-token',
            )
            parent_id = 'parent-http'
            queue = get_approval_queue(parent_id, workspace_root=root)
            request_id = queue.generate_request_id()
            queue._requests[request_id] = SubagentApprovalRequest(  # noqa: SLF001
                request_id=request_id,
                subagent_id='sub-http',
                parent_run_id=parent_id,
                subagent_name='worker',
                tool_name='workspace_write_file',
                tool_arguments={'path': 'a.py'},
                permission_mode='workspace-write',
                isolation='worktree',
                status=ApprovalRequestStatus.PENDING,
            )
            queue._persist(force=True)  # noqa: SLF001

            snapshot = remote.load_snapshot(parent_id)
            assert request_id in snapshot.requests

            ok = remote.update_request_status(
                parent_id,
                request_id,
                ApprovalRequestStatus.APPROVED,
                approved_by='http-client',
            )
            assert ok is True
            updated = file_backend.load_snapshot(parent_id)
            assert updated.requests[request_id]['status'] == 'approved'
        finally:
            server.stop()


def test_resolve_remote_http_backend(monkeypatch) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        server = ApprovalCoordinationHttpServer(
            FileBackedApprovalBackend(root),
            host='127.0.0.1',
            port=0,
        )
        server.start()
        try:
            monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', 'remote')
            monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_URL', server.base_url)
            backend = resolve_approval_backend(root)
            assert isinstance(backend, RemoteApprovalCoordinationBackend)
            assert backend.list_parent_run_ids() == []
        finally:
            server.stop()
