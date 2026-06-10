"""Hybrid approval coordination backend combining file and Redis backends."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from teaagent.coordination.approval_backend import (
    ApprovalQueuePruneReport,
    QueueDiskSnapshot,
)
from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_hybrid_store import (
    HybridApprovalQueueConfig,
    HybridApprovalQueueStore,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
    RedisApprovalQueueStore,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueueStore,
    default_hmac_secret,
)

logger = logging.getLogger(__name__)

BACKEND_HYBRID = 'hybrid'


class HybridApprovalCoordinationBackend:
    """Hybrid backend combining file-based and Redis coordination.

    This backend provides:
    - Fast reads from file-based storage
    - Fast writes to Redis with file backup
    - Automatic fallback between backends
    - Consistency validation and sync
    """

    def __init__(
        self,
        workspace_root: Path,
        *,
        hmac_secret: Optional[str] = None,
        redis_config: Optional[RedisApprovalQueueConfig] = None,
        redis_primary: bool = True,
        sync_interval_seconds: int = 60,
        enable_fallback: bool = True,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._hmac_secret = hmac_secret or default_hmac_secret()

        config = HybridApprovalQueueConfig(
            workspace_root=self._workspace_root,
            hmac_secret=self._hmac_secret,
            redis_config=redis_config,
            redis_primary=redis_primary,
            sync_interval_seconds=sync_interval_seconds,
            enable_fallback=enable_fallback,
        )

        self._store = HybridApprovalQueueStore(config)

    @property
    def backend_id(self) -> str:
        return BACKEND_HYBRID

    def load_snapshot(self, parent_run_id: str) -> QueueDiskSnapshot:
        """Load snapshot from file (primary) with Redis fallback."""
        try:
            return self._store.file_store.load(parent_run_id)
        except Exception as e:
            logger.error(f'File snapshot load failed: {e}')

        # Fallback: reconstruct from Redis
        if self._store.redis_available and self._store.redis_store:
            try:
                request_ids = self._store.redis_store.get_all_request_ids(parent_run_id)
                batch_ids = self._store.redis_store.get_all_batch_ids(parent_run_id)

                requests: dict[str, dict[str, Any]] = {}
                batches: dict[str, dict[str, Any]] = {}

                for request_id in request_ids:
                    request = self._store.redis_store.get_request(
                        parent_run_id, request_id
                    )
                    if request:
                        requests[request_id] = request.to_dict()

                for batch_id in batch_ids:
                    batch = self._store.redis_store.get_batch(parent_run_id, batch_id)
                    if batch:
                        batches[batch_id] = batch.to_dict()

                return QueueDiskSnapshot(parent_run_id, requests, batches)
            except Exception as e:
                logger.error(f'Redis snapshot load failed: {e}')

        return QueueDiskSnapshot(parent_run_id, {}, {})

    def save(
        self,
        parent_run_id: str,
        requests: dict[str, SubagentApprovalRequest],
        batches: dict[str, ApprovalBatch],
    ) -> None:
        """Save snapshot with dual-write strategy."""
        # Save requests
        for request in requests.values():
            self._store.save_request(parent_run_id, request)

        # Save batches
        for batch in batches.values():
            self._store.save_batch(parent_run_id, batch)

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        """Update request status with dual-write strategy."""
        return self._store.update_request_status(
            parent_run_id,
            request_id,
            status,
            reason=reason,
            approved_by=approved_by,
        )

    def list_parent_run_ids(self) -> list[str]:
        """List parent run IDs from file (primary) with Redis fallback."""
        return self._store.list_parent_run_ids()

    def exists(self, parent_run_id: str) -> bool:
        """Check if parent run exists in file with Redis fallback."""
        return self._store.exists(parent_run_id)

    def prune_stale(
        self,
        *,
        max_age_seconds: float,
        now: Optional[float] = None,
    ) -> ApprovalQueuePruneReport:
        """Prune stale artifacts from file and Redis."""
        # Prune from file
        file_report = self._store.file_store.prune_stale(
            max_age_seconds=max_age_seconds,
            now=now,
        )

        # Prune from Redis
        redis_deleted = 0
        if self._store.redis_available and self._store.redis_store:
            for parent_run_id in file_report.removed_parent_run_ids:
                try:
                    self._store.redis_store.delete_parent_run(parent_run_id)
                    redis_deleted += 1
                except Exception as e:
                    logger.error(f'Redis prune failed for {parent_run_id}: {e}')

        return ApprovalQueuePruneReport(
            removed_parent_run_ids=file_report.removed_parent_run_ids,
            skipped_pending=file_report.skipped_pending,
            skipped_recent=file_report.skipped_recent,
        )

    def sync_to_file(self, parent_run_id: str) -> dict:
        """Sync Redis state to file."""
        return self._store.sync_to_file(parent_run_id)

    def sync_to_redis(self, parent_run_id: str) -> dict:
        """Sync file state to Redis."""
        return self._store.sync_to_redis(parent_run_id)

    def validate_consistency(self, parent_run_id: str) -> dict:
        """Validate consistency between file and Redis backends."""
        return self._store.validate_consistency(parent_run_id)

    @property
    def redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._store.redis_available

    @property
    def file_store(self) -> ApprovalQueueStore:
        """Get the file store."""
        return self._store.file_store

    @property
    def redis_store(self) -> Optional[RedisApprovalQueueStore]:
        """Get the Redis store."""
        return self._store.redis_store
