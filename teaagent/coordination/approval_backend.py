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
BACKEND_HYBRID = 'hybrid'


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

    if selected == BACKEND_HYBRID:
        if workspace_root is None:
            raise ValueError('Workspace root is required for hybrid backend')

        from teaagent.coordination.approval_hybrid_backend import (
            HybridApprovalCoordinationBackend,
        )
        from teaagent.subagents._approval_queue_redis_store import (
            RedisApprovalQueueConfig,
        )
        from teaagent.subagents._circuit_breaker import CircuitBreakerConfig

        # Load Redis configuration from environment
        redis_host = os.environ.get('TEAAGENT_REDIS_HOST', 'localhost')
        redis_port = int(os.environ.get('TEAAGENT_REDIS_PORT', '6379'))
        redis_password = os.environ.get('TEAAGENT_REDIS_PASSWORD') or None
        redis_ssl = os.environ.get('TEAAGENT_REDIS_SSL', 'false').lower() == 'true'
        redis_primary = (
            os.environ.get('TEAAGENT_REDIS_PRIMARY', 'true').lower() == 'true'
        )
        sync_interval = int(os.environ.get('TEAAGENT_HYBRID_SYNC_INTERVAL', '60'))
        enable_fallback = (
            os.environ.get('TEAAGENT_HYBRID_FALLBACK', 'true').lower() == 'true'
        )
        enable_circuit_breaker = (
            os.environ.get('TEAAGENT_HYBRID_CIRCUIT_BREAKER', 'true').lower() == 'true'
        )
        enable_dynamic_sync = (
            os.environ.get('TEAAGENT_HYBRID_DYNAMIC_SYNC', 'true').lower() == 'true'
        )

        # Load circuit breaker configuration from environment
        cb_failure_threshold = int(
            os.environ.get('TEAAGENT_CIRCUIT_BREAKER_FAILURE_THRESHOLD', '5')
        )
        cb_timeout_seconds = int(
            os.environ.get('TEAAGENT_CIRCUIT_BREAKER_TIMEOUT_SECONDS', '60')
        )
        cb_success_threshold = int(
            os.environ.get('TEAAGENT_CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '2')
        )

        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=cb_failure_threshold,
            timeout_seconds=cb_timeout_seconds,
            success_threshold=cb_success_threshold,
        )

        redis_config = RedisApprovalQueueConfig(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            ssl=redis_ssl,
        )

        secret = hmac_secret if hmac_secret is not None else default_hmac_secret()
        return HybridApprovalCoordinationBackend(
            workspace_root=Path(workspace_root).resolve(),
            hmac_secret=secret,
            redis_config=redis_config,
            redis_primary=redis_primary,
            sync_interval_seconds=sync_interval,
            enable_fallback=enable_fallback,
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_config=circuit_breaker_config,
            enable_dynamic_sync=enable_dynamic_sync,
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
