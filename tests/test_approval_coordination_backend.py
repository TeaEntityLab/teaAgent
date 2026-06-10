"""Tests for durable approval coordination backends (WS2-005)."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.approval import ApprovalQueueStore, CentralizedApprovalQueue
from teaagent.coordination.approval_backend import (
    BACKEND_FILE,
    BACKEND_REMOTE,
    FileBackedApprovalBackend,
    RemoteApprovalCoordinationBackend,
    approval_backend_for_workspace,
    resolve_approval_backend,
)
from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
    get_approval_queue,
)


def test_resolve_file_backend_with_workspace() -> None:
    with TemporaryDirectory() as tmp:
        backend = resolve_approval_backend(Path(tmp))
        assert backend is not None
        assert backend.backend_id == BACKEND_FILE


def test_resolve_returns_none_without_workspace() -> None:
    assert resolve_approval_backend(None) is None


def test_file_backend_roundtrip_snapshot() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        backend = FileBackedApprovalBackend(root)
        parent_id = 'parent-backend'
        store = ApprovalQueueStore(root)
        path = store.queue_path(parent_id)
        path.write_text(
            '{"parent_run_id":"parent-backend","requests":{"r1":{"request_id":"r1",'
            '"subagent_id":"s","parent_run_id":"parent-backend","subagent_name":"w",'
            '"tool_name":"workspace_write_file","tool_arguments":{},'
            '"permission_mode":"prompt","isolation":"worktree","status":"pending"}},'
            '"batches":{}}\n',
            encoding='utf-8',
        )
        snapshot = backend.load_snapshot(parent_id)
        assert 'r1' in snapshot.requests
        assert backend.exists(parent_id)
        assert parent_id in backend.list_parent_run_ids()


def test_queue_recovery_after_registry_clear() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        parent_id = 'parent-recover'
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

        from teaagent.subagents import _approval_queue as mod

        mod._approval_queues.clear()
        recovered = get_approval_queue(parent_id, workspace_root=root)
        recovered.reload_from_store(force=True)
        assert len(recovered.get_pending_requests()) == 1


def test_remote_backend_requires_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', BACKEND_REMOTE)
    monkeypatch.delenv('TEAAGENT_APPROVAL_COORDINATION_URL', raising=False)
    with (
        TemporaryDirectory() as tmp,
        pytest.raises(ValueError, match='TEAAGENT_APPROVAL_COORDINATION_URL'),
    ):
        resolve_approval_backend(Path(tmp))


def test_remote_backend_stub_documents_extension_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', BACKEND_REMOTE)
    monkeypatch.setenv(
        'TEAAGENT_APPROVAL_COORDINATION_URL', 'https://approvals.example'
    )
    backend = resolve_approval_backend(Path('/tmp/workspace'))
    assert isinstance(backend, RemoteApprovalCoordinationBackend)
    with pytest.raises(NotImplementedError):
        backend.load_snapshot('parent-1')


def test_remote_backend_file_url_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_BACKEND', BACKEND_REMOTE)
        monkeypatch.setenv('TEAAGENT_APPROVAL_COORDINATION_URL', f'file://{root}')
        backend = resolve_approval_backend(root)
        assert isinstance(backend, RemoteApprovalCoordinationBackend)
        assert not backend.exists('missing-parent')


def test_approval_backend_for_workspace_never_none() -> None:
    with TemporaryDirectory() as tmp:
        backend = approval_backend_for_workspace(Path(tmp))
        assert backend.backend_id == BACKEND_FILE


def test_centralized_queue_uses_backend_not_raw_store() -> None:
    with TemporaryDirectory() as tmp:
        queue = CentralizedApprovalQueue('parent', workspace_root=Path(tmp))
        assert queue._backend is not None  # noqa: SLF001
        assert queue._backend.backend_id == BACKEND_FILE  # noqa: SLF001
