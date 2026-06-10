"""Hybrid approval queue store combining file-based and Redis backends."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

from cryptography.fernet import Fernet

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_metrics import (
    BackendType,
    MetricsContext,
    OperationType,
    get_metrics_collector,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
    RedisApprovalQueueStore,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueueStore,
    default_hmac_secret,
)
from teaagent.subagents._circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
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
    enable_circuit_breaker: bool = True  # Enable circuit breaker for Redis calls
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    enable_dynamic_sync: bool = True  # Enable dynamic sync interval adjustment
    min_sync_interval_seconds: int = 10  # Minimum sync interval
    max_sync_interval_seconds: int = 300  # Maximum sync interval
    enable_compression: bool = False  # Enable compression for large payloads
    compression_threshold_bytes: int = 1024  # Compress payloads larger than this
    enable_deduplication: bool = True  # Enable request deduplication
    deduplication_window_seconds: int = 300  # Deduplication time window
    enable_ttl: bool = True  # Enable TTL for requests
    default_ttl_seconds: int = 3600  # Default TTL for requests
    enable_priority: bool = False  # Enable priority queue support
    enable_health_check: bool = True  # Enable health check endpoint
    enable_rate_limiting: bool = False  # Enable rate limiting per subagent
    rate_limit_requests_per_minute: int = 60  # Rate limit per subagent
    enable_audit_trail: bool = True  # Enable audit trail for requests
    enable_encryption: bool = False  # Enable encryption for sensitive data
    enable_archival: bool = False  # Enable archival of old requests
    archival_age_days: int = 30  # Age before archival


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

        # Initialize circuit breaker for Redis calls
        self._circuit_breaker: Optional[CircuitBreaker] = None
        if config.enable_circuit_breaker and self._redis_store:
            self._circuit_breaker = CircuitBreaker(
                name='redis_approval_queue',
                config=config.circuit_breaker_config or CircuitBreakerConfig(),
            )
            logger.info('Circuit breaker enabled for Redis operations')

        # Initialize metrics
        self._metrics_collector = get_metrics_collector()
        self._metrics = self._metrics_collector.get_or_create_metrics(
            BackendType.HYBRID
        )

        # Deduplication tracking
        self._request_hashes: dict[str, float] = {}  # hash -> timestamp
        self._deduplication_lock: Optional[Any] = None

        # Rate limiting tracking
        self._rate_limit_tracker: defaultdict[str, list[float]] = defaultdict(
            list
        )  # subagent_id -> timestamps

        # Audit trail
        self._audit_trail: list[dict[str, Any]] = []

        # Encryption
        self._encryption_key: Optional[bytes] = None
        self._cipher: Optional[Fernet] = None
        if config.enable_encryption:
            self._encryption_key = Fernet.generate_key()
            self._cipher = Fernet(self._encryption_key)
            logger.info('Encryption enabled for sensitive data')

        # Dynamic sync state
        self._current_sync_interval = config.sync_interval_seconds
        self._last_sync_time: float = 0
        self._operation_latencies: list[float] = []
        self._max_latency_samples = 100

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

    def _call_redis(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute Redis call with circuit breaker protection."""
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(func, *args, **kwargs)
            except Exception as e:
                logger.warning(f'Circuit breaker blocked Redis call: {e}')
                self._redis_available = False
                raise
        else:
            return func(*args, **kwargs)

    def get_circuit_breaker_stats(self) -> Optional[dict]:
        """Get circuit breaker statistics."""
        if self._circuit_breaker:
            return self._circuit_breaker.get_stats()
        return None

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics for this store."""
        self._metrics.update_circuit_breaker_stats(self.get_circuit_breaker_stats())
        self._metrics.update_redis_availability(self._redis_available)
        return self._metrics.get_all_metrics()

    def _calculate_dynamic_sync_interval(self) -> int:
        """Calculate dynamic sync interval based on load."""
        if not self.config.enable_dynamic_sync:
            return self.config.sync_interval_seconds

        # Get operation metrics to determine load
        save_metrics = self._metrics.get_operation_metrics(OperationType.SAVE_REQUEST)
        update_metrics = self._metrics.get_operation_metrics(
            OperationType.UPDATE_REQUEST_STATUS
        )

        # Calculate operations per second
        total_ops = save_metrics.count + update_metrics.count
        if total_ops == 0:
            return self.config.sync_interval_seconds

        # Calculate rate based on avg latency
        avg_latency = (save_metrics.avg_latency_ms + update_metrics.avg_latency_ms) / 2

        # Higher load (more operations, lower latency) -> shorter sync interval
        # Lower load (fewer operations, higher latency) -> longer sync interval
        if avg_latency < 10:  # Very fast operations
            load_factor = 2.0
        elif avg_latency < 50:  # Fast operations
            load_factor = 1.5
        elif avg_latency < 100:  # Normal operations
            load_factor = 1.0
        elif avg_latency < 500:  # Slow operations
            load_factor = 0.5
        else:  # Very slow operations
            load_factor = 0.25

        # Calculate new interval
        new_interval = int(self.config.sync_interval_seconds / load_factor)

        # Clamp to min/max bounds
        new_interval = max(
            self.config.min_sync_interval_seconds,
            min(self.config.max_sync_interval_seconds, new_interval),
        )

        # Log if interval changed significantly
        if abs(new_interval - self._current_sync_interval) > 10:
            logger.info(
                f'Dynamic sync interval adjusted: {self._current_sync_interval}s -> {new_interval}s '
                f'(avg_latency: {avg_latency:.2f}ms, load_factor: {load_factor:.2f})'
            )

        self._current_sync_interval = new_interval
        return new_interval

    def should_sync(self) -> bool:
        """Check if sync should be performed based on dynamic interval."""
        if self._last_sync_time is None:
            return True

        import time

        elapsed = time.time() - self._last_sync_time
        sync_interval = self._calculate_dynamic_sync_interval()
        return elapsed >= sync_interval

    def record_sync(self) -> None:
        """Record that a sync was performed."""
        import time

        self._last_sync_time = time.time()

    def cleanup_orphaned_requests(
        self,
        max_age_seconds: float = 3600,
        timeout_seconds: float = 180,
    ) -> dict:
        """Clean up orphaned requests.

        Args:
            max_age_seconds: Maximum age for resolved requests before cleanup
            timeout_seconds: Timeout for pending requests before marking as timed out

        Returns:
            Cleanup report with counts of cleaned items
        """
        import time

        now = time.time()
        cleanup_report = {
            'timed_out_requests': 0,
            'expired_resolved_requests': 0,
            'orphaned_parent_runs': 0,
            'errors': 0,
        }

        try:
            # Get all parent run IDs
            parent_run_ids = self.list_parent_run_ids()

            for parent_run_id in parent_run_ids:
                try:
                    # Load snapshot
                    snapshot = self._file_store.load(parent_run_id)

                    # Check for orphaned parent run (no active references)
                    # This is a simple heuristic - in production, you might want to check
                    # against an active runs registry
                    pending_count = sum(
                        1
                        for r in snapshot.requests.values()
                        if r.get('status') == 'pending'
                    )

                    # If no pending requests and old, consider for cleanup
                    if pending_count == 0:
                        # Check age of the queue file
                        queue_path = self._file_store.queue_path(parent_run_id)
                        if (
                            queue_path.exists()
                            and (now - queue_path.stat().st_mtime) > max_age_seconds
                            and self.delete_parent_run(parent_run_id)
                        ):
                            cleanup_report['expired_resolved_requests'] += len(
                                snapshot.requests
                            )
                            cleanup_report['orphaned_parent_runs'] += 1
                        continue

                    # Check for timed out pending requests
                    for request_id, request_data in snapshot.requests.items():
                        if request_data.get('status') == 'pending':
                            created_at = request_data.get('created_at', '')
                            if created_at:
                                try:
                                    from datetime import datetime

                                    created_time = datetime.fromisoformat(created_at)
                                    age_seconds = now - created_time.timestamp()

                                    if age_seconds > timeout_seconds:
                                        # Mark as timed out
                                        self.update_request_status(
                                            parent_run_id,
                                            request_id,
                                            ApprovalRequestStatus.TIMEOUT,
                                            reason=f'Request timed out after {age_seconds:.0f}s',
                                        )
                                        cleanup_report['timed_out_requests'] += 1
                                except Exception as e:
                                    logger.error(
                                        f'Error parsing created_at for request {request_id}: {e}'
                                    )
                                    cleanup_report['errors'] += 1

                except Exception as e:
                    logger.error(f'Error cleaning up parent run {parent_run_id}: {e}')
                    cleanup_report['errors'] += 1

            logger.info(f'Cleanup completed: {cleanup_report}')
            return cleanup_report

        except Exception as e:
            logger.error(f'Cleanup failed: {e}')
            cleanup_report['errors'] += 1
            return cleanup_report

    def save_request(
        self,
        parent_run_id: str,
        request: SubagentApprovalRequest,
    ) -> None:
        """Save a request with dual-write strategy."""
        with MetricsContext(self._metrics, OperationType.SAVE_REQUEST):
            errors = []

            # Validate request
            is_valid, validation_errors = self.validate_request(request)
            if not is_valid:
                raise ValueError(f'Invalid request: {validation_errors}')

            # Check rate limit
            if not self._check_rate_limit(request.subagent_id):
                raise Exception(
                    f'Rate limit exceeded for subagent {request.subagent_id}'
                )

            # Check for duplicate
            if self._is_duplicate_request(request):
                logger.info(f'Skipping duplicate request: {request.request_id}')
                return

            # Add audit entry
            self._add_audit_entry('save_request', parent_run_id, request.request_id)

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Write to Redis first (primary)
                try:
                    self._call_redis(
                        self._redis_store.save_request, parent_run_id, request
                    )
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
                request_dict = request.to_dict()

                # Add TTL metadata if enabled
                if self.config.enable_ttl:
                    request_dict['ttl'] = self.config.default_ttl_seconds
                    request_dict['expires_at'] = (
                        time.time() + self.config.default_ttl_seconds
                    )

                # Compress if enabled
                if self.config.enable_compression:
                    request_json = json.dumps(request_dict)
                    compressed_data, is_compressed = self._compress_data(request_json)
                    if is_compressed:
                        request_dict['_compressed'] = True
                        request_dict['_data'] = compressed_data
                    else:
                        request_dict['_compressed'] = False

                # Encrypt if enabled
                if self.config.enable_encryption:
                    request_json = json.dumps(request_dict)
                    encrypted_data, is_encrypted = self._encrypt_data(request_json)
                    if is_encrypted:
                        request_dict['_encrypted'] = True
                        request_dict['_data'] = encrypted_data
                    else:
                        request_dict['_encrypted'] = False

                snapshot.requests[request.request_id] = request_dict
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
                    self._call_redis(
                        self._redis_store.save_request, parent_run_id, request
                    )
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
        with MetricsContext(self._metrics, OperationType.GET_REQUEST):
            # Try file first (faster)
            try:
                snapshot = self._file_store.load(parent_run_id)
                raw = snapshot.requests.get(request_id)
                if raw:
                    # Handle decryption
                    if raw.get('_encrypted'):
                        encrypted_data = raw.get('_data', '')
                        decrypted = self._decrypt_data(encrypted_data, True)
                        raw = json.loads(decrypted)
                        # Remove encryption metadata
                        raw.pop('_encrypted', None)
                        raw.pop('_data', None)

                    # Handle decompression
                    if raw.get('_compressed'):
                        compressed_data = raw.get('_data', '')
                        decompressed = self._decompress_data(compressed_data, True)
                        raw = json.loads(decompressed)
                        # Remove compression metadata
                        raw.pop('_compressed', None)
                        raw.pop('_data', None)

                    # Check TTL expiration
                    if (
                        self.config.enable_ttl
                        and raw.get('expires_at')
                        and time.time() > raw['expires_at']
                    ):
                        logger.info(f'Request {request_id} has expired (TTL)')
                        return None

                    from teaagent.subagents._approval_queue_store import (
                        request_from_dict,
                    )

                    return request_from_dict(raw)
            except Exception as e:
                logger.error(f'File read failed for request {request_id}: {e}')

            # Fallback to Redis
            if self._redis_available and self._redis_store:
                try:
                    return self._call_redis(
                        self._redis_store.get_request, parent_run_id, request_id
                    )
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
        with MetricsContext(self._metrics, OperationType.UPDATE_REQUEST_STATUS):
            errors = []

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Update Redis first (primary)
                try:
                    self._call_redis(
                        self._redis_store.update_request_status,
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
                    self._call_redis(
                        self._redis_store.update_request_status,
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
        with MetricsContext(self._metrics, OperationType.GET_PENDING_REQUESTS):
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
                    return self._call_redis(
                        self._redis_store.get_pending_requests, parent_run_id
                    )
                except Exception as e:
                    logger.error(f'Redis read failed for pending requests: {e}')

            return []

    def save_batch(
        self,
        parent_run_id: str,
        batch: ApprovalBatch,
    ) -> None:
        """Save a batch with dual-write strategy."""
        with MetricsContext(self._metrics, OperationType.SAVE_BATCH):
            errors = []

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Save to Redis first (primary)
                try:
                    self._call_redis(self._redis_store.save_batch, parent_run_id, batch)
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
                    self._call_redis(self._redis_store.save_batch, parent_run_id, batch)
                except Exception as e:
                    errors.append(f'Redis write failed: {e}')
                    logger.error(f'Redis write failed for batch {batch.batch_id}: {e}')
                    self._redis_available = False

            if errors and len(errors) >= 2:
                raise Exception(
                    f'All writes failed for batch {batch.batch_id}: {errors}'
                )

    def get_batch(
        self,
        parent_run_id: str,
        batch_id: str,
    ) -> Optional[ApprovalBatch]:
        """Get a batch from file with Redis fallback."""
        with MetricsContext(self._metrics, OperationType.GET_BATCH):
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
                    return self._call_redis(
                        self._redis_store.get_batch, parent_run_id, batch_id
                    )
                except Exception as e:
                    logger.error(f'Redis read failed for batch {batch_id}: {e}')

            return None

    def sync_to_file(self, parent_run_id: str) -> dict:
        """Sync Redis state to file."""
        with MetricsContext(self._metrics, OperationType.SYNC_TO_FILE):
            if not self._redis_available or not self._redis_store:
                return {'synced': 0, 'errors': 0, 'error': 'Redis not available'}

            try:
                # Get all requests from Redis
                request_ids = self._call_redis(
                    self._redis_store.get_all_request_ids, parent_run_id
                )
                batch_ids = self._call_redis(
                    self._redis_store.get_all_batch_ids, parent_run_id
                )

                synced = 0
                errors = 0

                # Sync requests
                for request_id in request_ids:
                    try:
                        request = self._call_redis(
                            self._redis_store.get_request, parent_run_id, request_id
                        )
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
                        batch = self._call_redis(
                            self._redis_store.get_batch, parent_run_id, batch_id
                        )
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
        with MetricsContext(self._metrics, OperationType.SYNC_TO_REDIS):
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
                        self._call_redis(
                            self._redis_store.save_request, parent_run_id, request
                        )
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
                        self._call_redis(
                            self._redis_store.save_batch, parent_run_id, batch
                        )
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
        with MetricsContext(self._metrics, OperationType.VALIDATE_CONSISTENCY):
            try:
                # Get request counts
                file_snapshot = self._file_store.load(parent_run_id)
                file_request_ids = set(file_snapshot.requests.keys())
                file_batch_ids = set(file_snapshot.batches.keys())

                redis_request_ids = set()
                redis_batch_ids = set()

                if self._redis_available and self._redis_store:
                    redis_request_ids = self._call_redis(
                        self._redis_store.get_all_request_ids, parent_run_id
                    )
                    redis_batch_ids = self._call_redis(
                        self._redis_store.get_all_batch_ids, parent_run_id
                    )

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
                return self._call_redis(self._redis_store.list_parent_run_ids)
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
                return self._call_redis(self._redis_store.exists, parent_run_id)
            except Exception as e:
                logger.error(f'Redis exists check failed: {e}')

        return False

    def delete_parent_run(self, parent_run_id: str) -> bool:
        """Delete parent run from both backends."""
        with MetricsContext(self._metrics, OperationType.DELETE_PARENT_RUN):
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
                    self._call_redis(self._redis_store.delete_parent_run, parent_run_id)
                except Exception as e:
                    errors.append(f'Redis delete failed: {e}')
                    logger.error(f'Redis delete failed for {parent_run_id}: {e}')

            if errors:
                logger.error(f'Delete errors for {parent_run_id}: {errors}')
                return False

            return True

    def _compress_data(self, data: str) -> tuple[str, bool]:
        """Compress data if enabled and above threshold."""
        if not self.config.enable_compression:
            return data, False

        data_bytes = data.encode('utf-8')
        if len(data_bytes) < self.config.compression_threshold_bytes:
            return data, False

        try:
            compressed = zlib.compress(data_bytes)
            # Only use compressed if it's actually smaller
            if len(compressed) < len(data_bytes):
                return compressed.decode('latin-1'), True
        except Exception as e:
            logger.warning(f'Compression failed: {e}')

        return data, False

    def _decompress_data(self, data: str, is_compressed: bool) -> str:
        """Decompress data if it was compressed."""
        if not is_compressed:
            return data

        try:
            compressed_bytes = data.encode('latin-1')
            decompressed = zlib.decompress(compressed_bytes)
            return decompressed.decode('utf-8')
        except Exception as e:
            logger.warning(f'Decompression failed: {e}')
            return data

    def _encrypt_data(self, data: str) -> tuple[str, bool]:
        """Encrypt data if encryption is enabled."""
        if not self.config.enable_encryption or self._cipher is None:
            return data, False

        try:
            data_bytes = data.encode('utf-8')
            encrypted = self._cipher.encrypt(data_bytes)
            return encrypted.decode('latin-1'), True
        except Exception as e:
            logger.warning(f'Encryption failed: {e}')
            return data, False

    def _decrypt_data(self, data: str, is_encrypted: bool) -> str:
        """Decrypt data if it was encrypted."""
        if not is_encrypted or self._cipher is None:
            return data

        try:
            encrypted_bytes = data.encode('latin-1')
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.warning(f'Decryption failed: {e}')
            return data

    def _compute_request_hash(self, request: SubagentApprovalRequest) -> str:
        """Compute hash for request deduplication."""
        hash_input = (
            f'{request.subagent_id}:{request.tool_name}:'
            f'{json.dumps(request.tool_arguments, sort_keys=True)}:'
            f'{request.permission_mode}:{request.isolation}'
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _is_duplicate_request(self, request: SubagentApprovalRequest) -> bool:
        """Check if request is a duplicate within deduplication window."""
        if not self.config.enable_deduplication:
            return False

        request_hash = self._compute_request_hash(request)
        current_time = time.time()

        # Clean up old hashes
        self._request_hashes = {
            h: t
            for h, t in self._request_hashes.items()
            if current_time - t < self.config.deduplication_window_seconds
        }

        # Check for duplicate
        if request_hash in self._request_hashes:
            logger.info(f'Duplicate request detected: {request.request_id}')
            return True

        # Store new hash
        self._request_hashes[request_hash] = current_time
        return False

    def health_check(self) -> dict[str, Any]:
        """Perform health check on the hybrid queue."""
        health: dict[str, Any] = {
            'status': 'healthy',
            'timestamp': time.time(),
            'components': {},
        }

        # Check file backend
        try:
            file_health = (
                self._file_store.health_check()
                if hasattr(self._file_store, 'health_check')
                else {'status': 'ok'}
            )
            health['components']['file'] = file_health
        except Exception as e:
            health['components']['file'] = {'status': 'error', 'error': str(e)}
            health['status'] = 'degraded'

        # Check Redis backend
        if self._redis_store:
            try:
                redis_available = self._check_redis_available()
                health['components']['redis'] = {
                    'status': 'ok' if redis_available else 'unavailable',
                    'available': redis_available,
                }
                if not redis_available:
                    health['status'] = 'degraded'
            except Exception as e:
                health['components']['redis'] = {'status': 'error', 'error': str(e)}
                health['status'] = 'degraded'

        # Check circuit breaker
        if self._circuit_breaker:
            stats = self.get_circuit_breaker_stats()
            health['components']['circuit_breaker'] = stats
            if stats and stats['state'] == 'open':
                health['status'] = 'degraded'

        # Check metrics
        try:
            metrics = self.get_metrics()
            health['components']['metrics'] = {
                'uptime_seconds': metrics.get('uptime_seconds', 0),
                'sync_errors': metrics.get('sync_errors', 0),
            }
        except Exception as e:
            health['components']['metrics'] = {'status': 'error', 'error': str(e)}

        return health

    def set_request_priority(
        self, parent_run_id: str, request_id: str, priority: int
    ) -> bool:
        """Set priority for a request (if priority queue enabled)."""
        if not self.config.enable_priority:
            logger.warning('Priority queue not enabled')
            return False

        try:
            # Load snapshot
            snapshot = self._file_store.load(parent_run_id)
            if request_id not in snapshot.requests:
                logger.warning(f'Request {request_id} not found')
                return False

            # Add priority metadata
            requests_dict = cast(dict[str, Any], snapshot.requests)
            requests_dict[request_id]['priority'] = priority
            requests_dict[request_id]['priority_set_at'] = time.time()

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            logger.info(f'Set priority {priority} for request {request_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to set priority: {e}')
            return False

    def get_pending_requests_by_priority(
        self, parent_run_id: str
    ) -> list[SubagentApprovalRequest]:
        """Get pending requests sorted by priority (if enabled)."""
        if not self.config.enable_priority:
            # Return regular pending requests
            return self.get_pending_requests(parent_run_id)

        try:
            snapshot = self._file_store.load(parent_run_id)
            pending = [
                r for r in snapshot.requests.values() if r.get('status') == 'pending'
            ]

            # Sort by priority (higher priority first)
            pending.sort(key=lambda r: r.get('priority', 0), reverse=True)

            from teaagent.subagents._approval_queue_store import (
                request_from_dict,
            )

            return [request_from_dict(r) for r in pending]
        except Exception as e:
            logger.error(f'Failed to get pending requests by priority: {e}')
            return []

    def validate_request(
        self, request: SubagentApprovalRequest
    ) -> tuple[bool, list[str]]:
        """Validate request against schema."""
        errors = []

        # Required fields
        if not request.request_id:
            errors.append('request_id is required')
        if not request.subagent_id:
            errors.append('subagent_id is required')
        if not request.tool_name:
            errors.append('tool_name is required')
        if not request.permission_mode:
            errors.append('permission_mode is required')

        # Validate tool_arguments is a dict
        if not isinstance(request.tool_arguments, dict):
            errors.append('tool_arguments must be a dictionary')

        # Validate isolation
        valid_isolations = ['shared', 'sandbox', 'isolated']
        if request.isolation not in valid_isolations:
            errors.append(f'isolation must be one of {valid_isolations}')

        # Validate permission_mode
        valid_modes = [
            'workspace-read',
            'workspace-write',
            'network',
            'system',
        ]
        if request.permission_mode not in valid_modes:
            errors.append(f'permission_mode must be one of {valid_modes}')

        # Validate timeout_seconds
        if request.timeout_seconds and request.timeout_seconds < 0:
            errors.append('timeout_seconds must be non-negative')

        return len(errors) == 0, errors

    def _check_rate_limit(self, subagent_id: str) -> bool:
        """Check if subagent is within rate limits."""
        if not self.config.enable_rate_limiting:
            return True

        current_time = time.time()
        minute_ago = current_time - 60

        # Clean up old timestamps
        self._rate_limit_tracker[subagent_id] = [
            ts for ts in self._rate_limit_tracker[subagent_id] if ts > minute_ago
        ]

        # Check rate limit
        request_count = len(self._rate_limit_tracker[subagent_id])
        if request_count >= self.config.rate_limit_requests_per_minute:
            logger.warning(
                f'Rate limit exceeded for subagent {subagent_id}: {request_count} requests/min'
            )
            return False

        # Record this request
        self._rate_limit_tracker[subagent_id].append(current_time)
        return True

    def _add_audit_entry(
        self,
        action: str,
        parent_run_id: str,
        request_id: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add entry to audit trail."""
        if not self.config.enable_audit_trail:
            return

        entry = {
            'timestamp': time.time(),
            'action': action,
            'parent_run_id': parent_run_id,
            'request_id': request_id,
            'details': details or {},
        }
        self._audit_trail.append(entry)

        # Keep audit trail size manageable
        if len(self._audit_trail) > 10000:
            self._audit_trail = self._audit_trail[-5000:]

    def get_audit_trail(
        self,
        parent_run_id: Optional[str] = None,
        request_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail entries."""
        if not self.config.enable_audit_trail:
            return []

        filtered = self._audit_trail
        if parent_run_id:
            filtered = [e for e in filtered if e['parent_run_id'] == parent_run_id]
        if request_id:
            filtered = [e for e in filtered if e['request_id'] == request_id]

        return filtered[-limit:]

    def cancel_request(self, parent_run_id: str, request_id: str, reason: str) -> bool:
        """Cancel a pending request."""
        try:
            snapshot = self._file_store.load(parent_run_id)
            if request_id not in snapshot.requests:
                logger.warning(f'Request {request_id} not found for cancellation')
                return False

            request_data = snapshot.requests[request_id]
            if request_data.get('status') != 'pending':
                logger.warning(
                    f'Cannot cancel non-pending request {request_id}: {request_data.get("status")}'
                )
                return False

            # Update status to cancelled
            request_data['status'] = 'cancelled'
            request_data['cancelled_at'] = time.time()
            request_data['cancellation_reason'] = reason

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            # Add audit entry
            self._add_audit_entry(
                'cancel_request',
                parent_run_id,
                request_id,
                {'reason': reason},
            )

            logger.info(f'Cancelled request {request_id}: {reason}')
            return True
        except Exception as e:
            logger.error(f'Failed to cancel request {request_id}: {e}')
            return False

    def search_requests(
        self,
        parent_run_id: str,
        *,
        subagent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[SubagentApprovalRequest]:
        """Search and filter requests."""
        try:
            snapshot = self._file_store.load(parent_run_id)
            results = []

            for _request_id, request_data in snapshot.requests.items():
                # Apply filters
                if subagent_id and request_data.get('subagent_id') != subagent_id:
                    continue
                if tool_name and request_data.get('tool_name') != tool_name:
                    continue
                if status and request_data.get('status') != status:
                    continue

                from teaagent.subagents._approval_queue_store import (
                    request_from_dict,
                )

                results.append(request_from_dict(request_data))

                if len(results) >= limit:
                    break

            return results
        except Exception as e:
            logger.error(f'Failed to search requests: {e}')
            return []

    def export_requests(self, parent_run_id: str, format: str = 'json') -> str:
        """Export requests from a parent run."""
        try:
            snapshot = self._file_store.load(parent_run_id)

            if format == 'json':
                return json.dumps(
                    {
                        'parent_run_id': parent_run_id,
                        'requests': snapshot.requests,
                        'batches': snapshot.batches,
                        'exported_at': time.time(),
                    },
                    indent=2,
                )
            else:
                raise ValueError(f'Unsupported export format: {format}')
        except Exception as e:
            logger.error(f'Failed to export requests: {e}')
            raise

    def import_requests(
        self, parent_run_id: str, data: str, format: str = 'json'
    ) -> int:
        """Import requests to a parent run."""
        try:
            if format == 'json':
                import_data = json.loads(data)
            else:
                raise ValueError(f'Unsupported import format: {format}')

            # Load existing snapshot
            snapshot = self._file_store.load(parent_run_id)

            # Merge requests
            imported_count = 0
            for request_id, request_data in import_data.get('requests', {}).items():
                if request_id not in snapshot.requests:
                    snapshot.requests[request_id] = request_data
                    imported_count += 1

            # Merge batches
            for batch_id, batch_data in import_data.get('batches', {}).items():
                if batch_id not in snapshot.batches:
                    snapshot.batches[batch_id] = batch_data

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            logger.info(f'Imported {imported_count} requests to {parent_run_id}')
            return imported_count
        except Exception as e:
            logger.error(f'Failed to import requests: {e}')
            raise

    def archive_old_requests(self, max_age_days: int = 30) -> dict[str, Any]:
        """Archive old requests to separate storage."""
        if not self.config.enable_archival:
            logger.warning('Archival not enabled')
            return {'archived': 0, 'errors': 0, 'archived_requests': []}

        archive_report: dict[str, Any] = {
            'archived': 0,
            'errors': 0,
            'archived_requests': [],
        }

        try:
            parent_run_ids = self.list_parent_run_ids()
            max_age_seconds = max_age_days * 86400

            for parent_run_id in parent_run_ids:
                try:
                    snapshot = self._file_store.load(parent_run_id)
                    current_time = time.time()

                    for _request_id, request_data in list(snapshot.requests.items()):
                        created_at = request_data.get('created_at', '')
                        if not created_at:
                            continue

                        try:
                            from datetime import datetime

                            created_time = datetime.fromisoformat(created_at)
                            age_seconds = current_time - created_time.timestamp()

                            if age_seconds > max_age_seconds:
                                # Archive request
                                archive_data = {
                                    'request_id': _request_id,
                                    'request_data': request_data,
                                    'archived_at': current_time,
                                    'parent_run_id': parent_run_id,
                                }

                                # Add to archive (in practice, this would go to separate storage)
                                archive_report['archived_requests'].append(archive_data)

                                # Remove from active queue
                                del snapshot.requests[_request_id]
                                archive_report['archived'] += 1

                        except Exception as e:
                            logger.warning(
                                f'Failed to archive request {_request_id}: {e}'
                            )
                            archive_report['errors'] += 1

                    # Save updated snapshot
                    if archive_report['archived'] > 0:
                        with self._file_store.lock(parent_run_id):
                            self._file_store._save_unlocked(parent_run_id, snapshot)

                except Exception as e:
                    logger.error(f'Failed to archive requests for {parent_run_id}: {e}')
                    archive_report['errors'] += 1

            logger.info(f'Archived {archive_report["archived"]} requests')
            return archive_report
        except Exception as e:
            logger.error(f'Failed to archive old requests: {e}')
            archive_report['errors'] += 1
            return archive_report

    def shutdown(self) -> None:
        """Gracefully shutdown the hybrid store."""
        logger.info('Shutting down hybrid approval queue store')

        # Sync any pending changes
        try:
            parent_run_ids = self.list_parent_run_ids()
            for parent_run_id in parent_run_ids:
                try:
                    if self._redis_available and self._redis_store:
                        self.sync_to_redis(parent_run_id)
                except Exception as e:
                    logger.warning(
                        f'Failed to sync {parent_run_id} during shutdown: {e}'
                    )
        except Exception as e:
            logger.error(f'Failed to sync during shutdown: {e}')

        # Close Redis connection if available
        if self._redis_store and hasattr(self._redis_store, 'close'):
            try:
                self._redis_store.close()
                logger.info('Redis connection closed')
            except Exception as e:
                logger.warning(f'Failed to close Redis connection: {e}')

        # Final metrics snapshot
        try:
            metrics = self.get_metrics()
            logger.info(f'Final metrics: {metrics}')
        except Exception as e:
            logger.warning(f'Failed to get final metrics: {e}')

        logger.info('Hybrid approval queue store shutdown complete')
