"""Durable approval coordination backends (WS2-005).

Local file-backed storage remains the default implementation. The protocol
supports crash recovery via snapshot reload and a remote extension point for
future orchestration services without changing ``CentralizedApprovalQueue``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueuePruneReport,
    ApprovalQueueStore,
    QueueDiskSnapshot,
    default_hmac_secret,
)

logger = logging.getLogger(__name__)

BACKEND_FILE = 'file'
BACKEND_REMOTE = 'remote'


@runtime_checkable
class ApprovalCoordinationBackend(Protocol):
    """Persistence and cross-process coordination for subagent approvals."""

    @property
    def backend_id(self) -> str:
        """Stable backend identifier (``file``, ``remote``, ...)."""

    def load_snapshot(self, parent_run_id: str) -> QueueDiskSnapshot:
        """Load durable queue state for recovery or cross-process reads."""

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        """Persist the full in-memory queue snapshot."""

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        """Atomically resolve a pending request (CLI/TUI cross-process path)."""

    def list_parent_run_ids(self) -> list[str]:
        """Return parent run IDs with durable queue artifacts."""

    def exists(self, parent_run_id: str) -> bool:
        """Return whether durable state exists for *parent_run_id*."""

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        """Remove resolved queue artifacts older than *max_age_seconds*."""


class FileBackedApprovalBackend:
    """Default local implementation backed by ``.teaagent/approval_queues/``."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        hmac_secret: Optional[str] = None,
    ) -> None:
        self._store = ApprovalQueueStore(
            Path(workspace_root).resolve(),
            hmac_secret=hmac_secret,
        )

    @property
    def backend_id(self) -> str:
        return BACKEND_FILE

    def load_snapshot(self, parent_run_id: str) -> QueueDiskSnapshot:
        return self._store.load(parent_run_id)

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        self._store.save(parent_run_id, requests, batches)

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        return self._store.update_request_status(
            parent_run_id,
            request_id,
            status,
            reason=reason,
            approved_by=approved_by,
        )

    def list_parent_run_ids(self) -> list[str]:
        return self._store.list_parent_run_ids()

    def exists(self, parent_run_id: str) -> bool:
        return self._store.exists(parent_run_id)

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        return self._store.prune_stale(max_age_seconds=max_age_seconds, now=now)

    def save_raw_snapshot(
        self,
        parent_run_id: str,
        requests: dict[str, dict[str, Any]],
        batches: dict[str, dict[str, Any]],
    ) -> None:
        """Persist queue JSON without reconstructing in-memory request objects."""
        self._store._save_unlocked(  # noqa: SLF001
            parent_run_id,
            QueueDiskSnapshot(parent_run_id, requests, batches),
        )


class RemoteApprovalCoordinationBackend:
    """Cross-process approval backend via ``file://`` or HTTP coordination service."""

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        hmac_secret: Optional[str] = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._auth_token = auth_token
        self._delegate: (
            FileBackedApprovalBackend
            | Any  # HttpApprovalCoordinationBackend
            | None
        )
        if self._base_url.startswith('file://'):
            workspace = Path(self._base_url[7:])
            self._delegate = FileBackedApprovalBackend(
                workspace,
                hmac_secret=hmac_secret,
            )
        elif self._base_url.startswith(('http://', 'https://')):
            from teaagent.coordination.approval_http_client import (
                HttpApprovalCoordinationBackend,
            )

            self._delegate = HttpApprovalCoordinationBackend(
                self._base_url,
                auth_token=auth_token,
            )
        else:
            self._delegate = None

    @property
    def backend_id(self) -> str:
        return BACKEND_REMOTE

    def _require_delegate(self) -> Any:
        if self._delegate is None:
            raise NotImplementedError(
                'Remote approval backend requires file:// or http(s):// URL. '
                'Set TEAAGENT_APPROVAL_COORDINATION_URL or use backend=file.'
            )
        return self._delegate

    def load_snapshot(self, parent_run_id: str) -> QueueDiskSnapshot:
        return self._require_delegate().load_snapshot(parent_run_id)

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        self._require_delegate().save(parent_run_id, requests, batches)

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        return self._require_delegate().update_request_status(
            parent_run_id,
            request_id,
            status,
            reason=reason,
            approved_by=approved_by,
        )

    def list_parent_run_ids(self) -> list[str]:
        return self._require_delegate().list_parent_run_ids()

    def exists(self, parent_run_id: str) -> bool:
        return self._require_delegate().exists(parent_run_id)

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        return self._require_delegate().prune_stale(
            max_age_seconds=max_age_seconds,
            now=now,
        )


def resolve_approval_backend(
    workspace_root: Optional[Path],
    *,
    backend_id: Optional[str] = None,
    hmac_secret: Optional[str] = None,
) -> Optional[ApprovalCoordinationBackend]:
    """Select the durable approval backend for a workspace.

    Returns ``None`` when no workspace root is available (process-local queue only).
    """
    selected = (
        (
            backend_id
            or os.environ.get('TEAAGENT_APPROVAL_COORDINATION_BACKEND')
            or BACKEND_FILE
        )
        .strip()
        .lower()
    )

    if selected == BACKEND_REMOTE:
        base_url = os.environ.get('TEAAGENT_APPROVAL_COORDINATION_URL', '').strip()
        if not base_url:
            raise ValueError(
                'TEAAGENT_APPROVAL_COORDINATION_URL is required when '
                'TEAAGENT_APPROVAL_COORDINATION_BACKEND=remote'
            )
        token = os.environ.get('TEAAGENT_APPROVAL_COORDINATION_TOKEN') or None
        secret = hmac_secret if hmac_secret is not None else default_hmac_secret()
        return RemoteApprovalCoordinationBackend(
            base_url,
            auth_token=token,
            hmac_secret=secret,
        )

    if workspace_root is None:
        return None

    secret = hmac_secret if hmac_secret is not None else default_hmac_secret()
    return FileBackedApprovalBackend(
        Path(workspace_root).resolve(),
        hmac_secret=secret,
    )


def approval_backend_for_workspace(
    workspace_root: Path,
    *,
    backend_id: Optional[str] = None,
) -> ApprovalCoordinationBackend:
    """Return a durable backend for *workspace_root* (never ``None``)."""
    backend = resolve_approval_backend(workspace_root, backend_id=backend_id)
    if backend is None:
        backend = FileBackedApprovalBackend(Path(workspace_root).resolve())
    return backend
