"""Backend operations mixin (Redis, sync, consistency) for hybrid approval queue store."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
)
from teaagent.subagents._approval_queue_metrics import (
    MetricsContext,
    OperationType,
)
from teaagent.subagents._hybrid_store_base import HybridStoreBase

logger = logging.getLogger(__name__)


class HybridStoreBackendsMixin(HybridStoreBase):
    """Mixin providing backends operations for HybridApprovalQueueStore."""

    def _check_redis_available(self) -> bool:
        """Check if Redis is available."""
        if self._redis_store is None:
            return False
        try:
            return self._redis_store.ping()
        except Exception as e:
            logger.warning(f'Redis not available: {e}')
            return False

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

    def sync_to_file(self, parent_run_id: str) -> dict:
        """Sync Redis state to file."""
        start_time = time.perf_counter()
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

                # Adjust sync interval based on operation latency
                operation_latency = time.perf_counter() - start_time
                self._adjust_sync_interval(operation_latency)

                return {'synced': synced, 'errors': errors}
            except Exception as e:
                logger.error(f'Sync to file failed: {e}')
                return {'synced': 0, 'errors': 0, 'error': str(e)}

    def sync_to_redis(self, parent_run_id: str) -> dict:
        """Sync file state to Redis."""
        start_time = time.perf_counter()
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

                # Adjust sync interval based on operation latency
                operation_latency = time.perf_counter() - start_time
                self._adjust_sync_interval(operation_latency)

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

    def validate_global_consistency(self) -> dict[str, Any]:
        """Validate consistency between Redis and file backends globally.

        Returns:
            Dictionary with consistency metrics and details
        """
        consistency_report: dict[str, Any] = {
            'timestamp': time.time(),
            'redis_available': self._redis_available,
            'file_available': True,
            'total_redis_requests': 0,
            'total_file_requests': 0,
            'missing_in_redis': 0,
            'missing_in_file': 0,
            'inconsistent_requests': 0,
            'consistency_rate': 0.0,
            'details': [],
        }

        try:
            if not self._redis_store:
                consistency_report['redis_available'] = False
                consistency_report['details'].append('Redis store not available')
                return consistency_report

            # Get all request IDs from both backends
            redis_request_ids: set[str] = set()
            file_request_ids: set[str] = set()

            # Get Redis request IDs
            redis_parent_runs = self._redis_store.list_parent_run_ids()
            for parent_run_id in redis_parent_runs:
                try:
                    request_ids = self._redis_store.get_all_request_ids(parent_run_id)
                    redis_request_ids.update(request_ids)
                except Exception as e:
                    consistency_report['details'].append(
                        f'Failed to get Redis requests for {parent_run_id}: {e}'
                    )

            # Get file request IDs
            file_parent_runs = self._file_store.list_parent_run_ids()
            for parent_run_id in file_parent_runs:
                try:
                    snapshot = self._file_store.load(parent_run_id)
                    file_request_ids.update(snapshot.requests.keys())
                except Exception as e:
                    consistency_report['details'].append(
                        f'Failed to get file requests for {parent_run_id}: {e}'
                    )

            consistency_report['total_redis_requests'] = len(redis_request_ids)
            consistency_report['total_file_requests'] = len(file_request_ids)

            # Find missing requests
            missing_in_redis = file_request_ids - redis_request_ids
            missing_in_file = redis_request_ids - file_request_ids

            consistency_report['missing_in_redis'] = len(missing_in_redis)
            consistency_report['missing_in_file'] = len(missing_in_file)

            # Check for inconsistent request data
            common_requests = redis_request_ids & file_request_ids
            inconsistent_count = 0

            # Note: Full data consistency check would require comparing request data
            # For now, we just check for missing requests
            consistency_report['inconsistent_requests'] = inconsistent_count

            # Calculate consistency rate
            total_unique = len(redis_request_ids | file_request_ids)
            if total_unique > 0:
                matching = len(common_requests)
                consistency_report['consistency_rate'] = matching / total_unique
            else:
                consistency_report['consistency_rate'] = 1.0

            # Add details
            if missing_in_redis:
                consistency_report['details'].append(
                    f'{len(missing_in_redis)} requests missing in Redis'
                )
            if missing_in_file:
                consistency_report['details'].append(
                    f'{len(missing_in_file)} requests missing in file'
                )
            if consistency_report['consistency_rate'] < 0.99:
                consistency_report['details'].append(
                    f'Consistency rate below 99%: {consistency_report["consistency_rate"]:.2%}'
                )

        except Exception as e:
            logger.error(f'Consistency validation failed: {e}')
            consistency_report['error'] = str(e)

        return consistency_report

    def _adjust_sync_interval(self, operation_latency: float) -> None:
        """Dynamically adjust sync interval based on operation latency.

        Args:
            operation_latency: Latency of the last operation in seconds
        """
        if not self.config.enable_dynamic_sync:
            return

        # Add latency to samples
        self._operation_latencies.append(operation_latency)
        if len(self._operation_latencies) > self._max_latency_samples:
            self._operation_latencies.pop(0)

        # Calculate average latency
        if len(self._operation_latencies) < 10:
            return  # Need more samples

        avg_latency = sum(self._operation_latencies) / len(self._operation_latencies)

        # Adjust sync interval based on latency
        # Higher latency -> longer sync interval to reduce load
        # Lower latency -> shorter sync interval for better consistency
        if avg_latency > 1.0:  # High latency
            target_interval = min(
                self._current_sync_interval * 1.5, self.config.max_sync_interval_seconds
            )
        elif avg_latency > 0.5:  # Medium latency
            target_interval = min(
                self._current_sync_interval * 1.1, self.config.max_sync_interval_seconds
            )
        elif avg_latency < 0.1:  # Low latency
            target_interval = max(
                self._current_sync_interval * 0.9, self.config.min_sync_interval_seconds
            )
        else:
            target_interval = self._current_sync_interval

        # Apply change gradually
        self._current_sync_interval = int(target_interval)

        logger.debug(
            f'Adjusted sync interval to {self._current_sync_interval}s '
            f'(avg latency: {avg_latency:.3f}s)'
        )

    def get_current_sync_interval(self) -> int:
        """Get the current sync interval.

        Returns:
            Current sync interval in seconds
        """
        return self._current_sync_interval

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
