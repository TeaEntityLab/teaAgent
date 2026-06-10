"""Hybrid approval queue store combining file-based and Redis backends."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
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


@dataclass
class HybridApprovalQueueConfig:
    """Configuration for hybrid approval queue."""

    workspace_root: Path
    hmac_secret: Optional[str] = None
    redis_config: Optional[RedisApprovalQueueConfig] = None
    redis_primary: bool = True  # If True, Redis is primary for writes
    sync_interval_seconds: int = 60
    enable_fallback: bool = True  # Enable fallback to file if Redis fails


class HybridApprovalQueueStore:
    """Hybrid approval queue combining file-based and Redis backends.

    Write Strategy:
    - If redis_primary=True: Write to Redis first, then file (backup)
    - If redis_primary=False: Write to file first, then Redis (backup)
    - Fallback: If primary fails, fall back to secondary

    Read Strategy:
    - Read from file (faster for read operations)
    - Optional: Read from Redis if file fails

    Sync Strategy:
    - Periodic sync between backends
    - On-demand sync for specific requests
    - Consistency validation
    """

    def __init__(
        self,
        config: HybridApprovalQueueConfig,
        file_store: Optional[ApprovalQueueStore] = None,
        redis_store: Optional[RedisApprovalQueueStore] = None,
    ) -> None:
        self.config = config
        self._file_store = file_store or ApprovalQueueStore(
            workspace_root=config.workspace_root,
            hmac_secret=config.hmac_secret or default_hmac_secret(),
        )
        self._redis_client: Optional[Any] = None
        self._redis_store: Optional[RedisApprovalQueueStore] = None

        if redis_store:
            self._redis_store = redis_store
        elif config.redis_config:
            self._redis_store = RedisApprovalQueueStore(config=config.redis_config)

        self._redis_available = self._check_redis_available()
        self._sync_errors = 0
        self._max_sync_errors = 5

    def _check_redis_available(self) -> bool:
        """Check if Redis is available."""
        if self._redis_store is None:
            return False
        try:
            return self._redis_store.ping()
        except Exception as e:
            logger.warning(f'Redis not available: {e}')
            return False

    @property
    def redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis_available

    @property
    def file_store(self) -> ApprovalQueueStore:
        """Get the file store."""
        return self._file_store

    @property
    def redis_store(self) -> Optional[RedisApprovalQueueStore]:
        """Get the Redis store."""
        return self._redis_store

    def save_request(
        self,
        parent_run_id: str,
        request: SubagentApprovalRequest,
    ) -> None:
        """Save a request with dual-write strategy."""
        errors = []

        if self.config.redis_primary and self._redis_available and self._redis_store:
            # Write to Redis first (primary)
            try:
                self._redis_store.save_request(parent_run_id, request)
            except Exception as e:
                errors.append(f'Redis write failed: {e}')
                logger.error(
                    f'Redis write failed for request {request.request_id}: {e}'
                )
                self._redis_available = False

        # Write to file (backup or primary)
        try:
            # Load existing snapshot, add request, save back
            snapshot = self._file_store.load(parent_run_id)
            snapshot.requests[request.request_id] = request.to_dict()
            # Use internal save method with snapshot
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)
        except Exception as e:
            errors.append(f'File write failed: {e}')
            logger.error(f'File write failed for request {request.request_id}: {e}')

        if (
            not self.config.redis_primary
            and self._redis_available
            and self._redis_store
        ):
            # Write to Redis (backup)
            try:
                self._redis_store.save_request(parent_run_id, request)
            except Exception as e:
                errors.append(f'Redis write failed: {e}')
                logger.error(
                    f'Redis write failed for request {request.request_id}: {e}'
                )
                self._redis_available = False

        if errors and len(errors) >= 2:
            raise Exception(
                f'All writes failed for request {request.request_id}: {errors}'
            )

    def get_request(
        self,
        parent_run_id: str,
        request_id: str,
    ) -> Optional[SubagentApprovalRequest]:
        """Get a request from file (primary) with Redis fallback."""
        # Try file first (faster)
        try:
            snapshot = self._file_store.load(parent_run_id)
            raw = snapshot.requests.get(request_id)
            if raw:
                from teaagent.subagents._approval_queue_store import request_from_dict

                return request_from_dict(raw)
        except Exception as e:
            logger.error(f'File read failed for request {request_id}: {e}')

        # Fallback to Redis
        if self._redis_available and self._redis_store:
            try:
                return self._redis_store.get_request(parent_run_id, request_id)
            except Exception as e:
                logger.error(f'Redis read failed for request {request_id}: {e}')

        return None

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
        errors = []

        if self.config.redis_primary and self._redis_available and self._redis_store:
            # Update Redis first (primary)
            try:
                self._redis_store.update_request_status(
                    parent_run_id,
                    request_id,
                    status,
                    reason=reason,
                    approved_by=approved_by,
                )
            except Exception as e:
                errors.append(f'Redis update failed: {e}')
                logger.error(f'Redis update failed for request {request_id}: {e}')
                self._redis_available = False

        # Update file (backup or primary)
        try:
            self._file_store.update_request_status(
                parent_run_id,
                request_id,
                status,
                reason=reason,
                approved_by=approved_by,
            )
        except Exception as e:
            errors.append(f'File update failed: {e}')
            logger.error(f'File update failed for request {request_id}: {e}')

        if (
            not self.config.redis_primary
            and self._redis_available
            and self._redis_store
        ):
            # Update Redis (backup)
            try:
                self._redis_store.update_request_status(
                    parent_run_id,
                    request_id,
                    status,
                    reason=reason,
                    approved_by=approved_by,
                )
            except Exception as e:
                errors.append(f'Redis update failed: {e}')
                logger.error(f'Redis update failed for request {request_id}: {e}')
                self._redis_available = False

        if errors and len(errors) >= 2:
            logger.error(f'All updates failed for request {request_id}: {errors}')
            return False

        return True

    def get_pending_requests(
        self,
        parent_run_id: str,
    ) -> list[SubagentApprovalRequest]:
        """Get pending requests from file (faster)."""
        try:
            snapshot = self._file_store.load(parent_run_id)
            from teaagent.subagents._approval_queue_store import (
                pending_requests_from_snapshot,
            )

            return pending_requests_from_snapshot(snapshot)
        except Exception as e:
            logger.error(f'File read failed for pending requests: {e}')

        # Fallback to Redis
        if self._redis_available and self._redis_store:
            try:
                return self._redis_store.get_pending_requests(parent_run_id)
            except Exception as e:
                logger.error(f'Redis read failed for pending requests: {e}')

        return []

    def save_batch(
        self,
        parent_run_id: str,
        batch: ApprovalBatch,
    ) -> None:
        """Save a batch with dual-write strategy."""
        errors = []

        if self.config.redis_primary and self._redis_available and self._redis_store:
            # Save to Redis first (primary)
            try:
                self._redis_store.save_batch(parent_run_id, batch)
            except Exception as e:
                errors.append(f'Redis write failed: {e}')
                logger.error(f'Redis write failed for batch {batch.batch_id}: {e}')
                self._redis_available = False

        # Save to file (backup or primary)
        try:
            # Load existing snapshot, add batch, save back
            snapshot = self._file_store.load(parent_run_id)
            snapshot.batches[batch.batch_id] = batch.to_dict()
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)
        except Exception as e:
            errors.append(f'File write failed: {e}')
            logger.error(f'File write failed for batch {batch.batch_id}: {e}')

        if (
            not self.config.redis_primary
            and self._redis_available
            and self._redis_store
        ):
            # Save to Redis (backup)
            try:
                self._redis_store.save_batch(parent_run_id, batch)
            except Exception as e:
                errors.append(f'Redis write failed: {e}')
                logger.error(f'Redis write failed for batch {batch.batch_id}: {e}')
                self._redis_available = False

        if errors and len(errors) >= 2:
            raise Exception(f'All writes failed for batch {batch.batch_id}: {errors}')

    def get_batch(
        self,
        parent_run_id: str,
        batch_id: str,
    ) -> Optional[ApprovalBatch]:
        """Get a batch from file with Redis fallback."""
        # Try file first
        try:
            snapshot = self._file_store.load(parent_run_id)
            raw = snapshot.batches.get(batch_id)
            if raw:
                # ApprovalBatch doesn't have from_dict, reconstruct manually
                batch = ApprovalBatch(
                    batch_id=raw.get('batch_id', batch_id),
                    parent_run_id=raw.get('parent_run_id', parent_run_id),
                    created_at=raw.get('created_at', ''),
                    status=ApprovalRequestStatus(raw.get('status', 'pending')),
                )
                return batch
        except Exception as e:
            logger.error(f'File read failed for batch {batch_id}: {e}')

        # Fallback to Redis
        if self._redis_available and self._redis_store:
            try:
                return self._redis_store.get_batch(parent_run_id, batch_id)
            except Exception as e:
                logger.error(f'Redis read failed for batch {batch_id}: {e}')

        return None

    def sync_to_file(self, parent_run_id: str) -> dict:
        """Sync Redis state to file."""
        if not self._redis_available or not self._redis_store:
            return {'synced': 0, 'errors': 0, 'error': 'Redis not available'}

        try:
            # Get all requests from Redis
            request_ids = self._redis_store.get_all_request_ids(parent_run_id)
            batch_ids = self._redis_store.get_all_batch_ids(parent_run_id)

            synced = 0
            errors = 0

            # Sync requests
            for request_id in request_ids:
                try:
                    request = self._redis_store.get_request(parent_run_id, request_id)
                    if request:
                        # Load existing snapshot, add request, save back
                        snapshot = self._file_store.load(parent_run_id)
                        snapshot.requests[request_id] = request.to_dict()
                        with self._file_store.lock(parent_run_id):
                            self._file_store._save_unlocked(parent_run_id, snapshot)
                        synced += 1
                except Exception as e:
                    logger.error(f'Sync failed for request {request_id}: {e}')
                    errors += 1

            # Sync batches
            for batch_id in batch_ids:
                try:
                    batch = self._redis_store.get_batch(parent_run_id, batch_id)
                    if batch:
                        # Load existing snapshot, add batch, save back
                        snapshot = self._file_store.load(parent_run_id)
                        snapshot.batches[batch_id] = batch.to_dict()
                        with self._file_store.lock(parent_run_id):
                            self._file_store._save_unlocked(parent_run_id, snapshot)
                        synced += 1
                except Exception as e:
                    logger.error(f'Sync failed for batch {batch_id}: {e}')
                    errors += 1

            return {'synced': synced, 'errors': errors}
        except Exception as e:
            logger.error(f'Sync to file failed: {e}')
            return {'synced': 0, 'errors': 0, 'error': str(e)}

    def sync_to_redis(self, parent_run_id: str) -> dict:
        """Sync file state to Redis."""
        if not self._redis_available or not self._redis_store:
            return {'synced': 0, 'errors': 0, 'error': 'Redis not available'}

        try:
            snapshot = self._file_store.load(parent_run_id)

            synced = 0
            errors = 0

            # Sync requests
            for request_id, raw in snapshot.requests.items():
                try:
                    from teaagent.subagents._approval_queue_store import (
                        request_from_dict,
                    )

                    request = request_from_dict(raw)
                    self._redis_store.save_request(parent_run_id, request)
                    synced += 1
                except Exception as e:
                    logger.error(f'Sync failed for request {request_id}: {e}')
                    errors += 1

            # Sync batches
            for batch_id, raw in snapshot.batches.items():
                try:
                    batch = ApprovalBatch(
                        batch_id=raw.get('batch_id', batch_id),
                        parent_run_id=raw.get('parent_run_id', parent_run_id),
                        created_at=raw.get('created_at', ''),
                        status=ApprovalRequestStatus(raw.get('status', 'pending')),
                    )
                    self._redis_store.save_batch(parent_run_id, batch)
                    synced += 1
                except Exception as e:
                    logger.error(f'Sync failed for batch {batch_id}: {e}')
                    errors += 1

            return {'synced': synced, 'errors': errors}
        except Exception as e:
            logger.error(f'Sync to Redis failed: {e}')
            return {'synced': 0, 'errors': 0, 'error': str(e)}

    def validate_consistency(self, parent_run_id: str) -> dict:
        """Validate consistency between file and Redis backends."""
        try:
            # Get request counts
            file_snapshot = self._file_store.load(parent_run_id)
            file_request_ids = set(file_snapshot.requests.keys())
            file_batch_ids = set(file_snapshot.batches.keys())

            redis_request_ids = set()
            redis_batch_ids = set()

            if self._redis_available and self._redis_store:
                redis_request_ids = self._redis_store.get_all_request_ids(parent_run_id)
                redis_batch_ids = self._redis_store.get_all_batch_ids(parent_run_id)

            # If Redis is not available, consider it consistent (no discrepancy to measure)
            if not self._redis_available or not self._redis_store:
                return {
                    'file_requests': len(file_request_ids),
                    'redis_requests': 0,
                    'file_batches': len(file_batch_ids),
                    'redis_batches': 0,
                    'missing_in_redis': 0,
                    'missing_in_file': 0,
                    'consistency_rate': 1.0,
                    'redis_available': False,
                }

            # Calculate consistency
            missing_in_redis = file_request_ids - redis_request_ids
            missing_in_file = redis_request_ids - file_request_ids

            total = max(len(file_request_ids), len(redis_request_ids))
            consistency_rate = 1.0
            if total > 0:
                consistency_rate = (
                    1.0 - (len(missing_in_redis) + len(missing_in_file)) / total
                )
            else:
                # Both empty, consider consistent
                consistency_rate = 1.0

            return {
                'file_requests': len(file_request_ids),
                'redis_requests': len(redis_request_ids),
                'file_batches': len(file_batch_ids),
                'redis_batches': len(redis_batch_ids),
                'missing_in_redis': len(missing_in_redis),
                'missing_in_file': len(missing_in_file),
                'consistency_rate': consistency_rate,
                'redis_available': True,
            }
        except Exception as e:
            logger.error(f'Consistency validation failed: {e}')
            return {
                'error': str(e),
                'consistency_rate': 0.0,
                'redis_available': self._redis_available,
            }

    def list_parent_run_ids(self) -> list[str]:
        """List parent run IDs from file (primary) with Redis fallback."""
        try:
            return self._file_store.list_parent_run_ids()
        except Exception as e:
            logger.error(f'File list failed: {e}')

        if self._redis_available and self._redis_store:
            try:
                return self._redis_store.list_parent_run_ids()
            except Exception as e:
                logger.error(f'Redis list failed: {e}')

        return []

    def exists(self, parent_run_id: str) -> bool:
        """Check if parent run exists in file with Redis fallback."""
        try:
            return self._file_store.exists(parent_run_id)
        except Exception as e:
            logger.error(f'File exists check failed: {e}')

        if self._redis_available and self._redis_store:
            try:
                return self._redis_store.exists(parent_run_id)
            except Exception as e:
                logger.error(f'Redis exists check failed: {e}')

        return False

    def delete_parent_run(self, parent_run_id: str) -> bool:
        """Delete parent run from both backends."""
        errors = []

        # Delete from file
        try:
            path = self._file_store.queue_path(parent_run_id)
            if path.exists():
                path.unlink(missing_ok=True)
        except Exception as e:
            errors.append(f'File delete failed: {e}')
            logger.error(f'File delete failed for {parent_run_id}: {e}')

        # Delete from Redis
        if self._redis_available and self._redis_store:
            try:
                self._redis_store.delete_parent_run(parent_run_id)
            except Exception as e:
                errors.append(f'Redis delete failed: {e}')
                logger.error(f'Redis delete failed for {parent_run_id}: {e}')

        if errors:
            logger.error(f'Delete errors for {parent_run_id}: {errors}')
            return False

        return True
