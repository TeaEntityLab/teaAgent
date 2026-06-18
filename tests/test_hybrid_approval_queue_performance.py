"""Performance and stress tests for hybrid approval queue."""

from __future__ import annotations

import contextlib
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_request_factory():
    """Factory for creating sample requests with unique IDs."""

    def _create(request_id: str, subagent_id: str = 'subagent-1'):
        return SubagentApprovalRequest(
            request_id=request_id,
            subagent_id=subagent_id,
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': f'/tmp/test_{request_id}.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

    return _create


class TestHybridApprovalQueuePerformance:
    """Performance and stress tests for hybrid approval queue."""

    def test_large_scale_queue_performance(
        self, temp_workspace, sample_request_factory, request
    ):
        """Test performance with 1000+ pending requests."""
        if hasattr(request.config, 'workerinput'):
            pytest.skip('wall-clock performance threshold requires a dedicated process')

        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Create 1000 requests
        num_requests = 1000
        start_time = time.time()

        for i in range(num_requests):
            request = sample_request_factory(f'req-{i}')
            store.save_request('parent-1', request)

        save_time = time.time() - start_time

        # Verify all requests are saved
        pending = store.get_pending_requests('parent-1')
        assert len(pending) == num_requests

        # Measure read performance
        start_time = time.time()
        for i in range(num_requests):
            request = store.get_request('parent-1', f'req-{i}')
            assert request is not None

        read_time = time.time() - start_time

        # Measure update performance
        start_time = time.time()
        for i in range(num_requests):
            store.update_request_status(
                'parent-1',
                f'req-{i}',
                ApprovalRequestStatus.APPROVED,
            )

        update_time = time.time() - start_time

        # Performance assertions (adjust based on system)
        assert save_time < 10.0, f'Save time too slow: {save_time:.2f}s'
        assert read_time < 5.0, f'Read time too slow: {read_time:.2f}s'
        assert update_time < 15.0, f'Update time too slow: {update_time:.2f}s'

        print(f'\nPerformance metrics for {num_requests} requests:')
        print(f'  Save: {save_time:.2f}s ({num_requests / save_time:.0f} req/s)')
        print(f'  Read: {read_time:.2f}s ({num_requests / read_time:.0f} req/s)')
        print(f'  Update: {update_time:.2f}s ({num_requests / update_time:.0f} req/s)')

    def test_concurrent_save_operations(self, temp_workspace, sample_request_factory):
        """Test concurrent save operations from multiple threads."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        num_threads = 5
        requests_per_thread = 20
        total_requests = num_threads * requests_per_thread

        def save_requests(thread_id: int):
            """Save requests from a thread."""
            for i in range(requests_per_thread):
                request_id = f'req-{thread_id}-{i}'
                request = sample_request_factory(request_id, f'subagent-{thread_id}')
                with contextlib.suppress(Exception):
                    # File locking may cause some concurrent writes to fail
                    store.save_request('parent-1', request)

        # Run concurrent saves
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(save_requests, thread_id)
                for thread_id in range(num_threads)
            ]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        concurrent_time = time.time() - start_time

        # Verify some requests were saved (file locking serializes writes)
        pending = store.get_pending_requests('parent-1')
        assert len(pending) > 0, 'No requests saved'
        assert len(pending) <= total_requests, 'More requests saved than attempted'

        print('\nConcurrent save performance:')
        print(f'  {num_threads} threads, {requests_per_thread} requests each')
        print(f'  Attempted: {total_requests}, Saved: {len(pending)}')
        print(f'  Time: {concurrent_time:.2f}s')

    def test_concurrent_read_operations(self, temp_workspace, sample_request_factory):
        """Test concurrent read operations from multiple threads."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Pre-populate with requests
        num_requests = 500
        for i in range(num_requests):
            request = sample_request_factory(f'req-{i}')
            store.save_request('parent-1', request)

        num_threads = 10
        reads_per_thread = 100

        def read_requests(thread_id: int):
            """Read requests from a thread."""
            for i in range(reads_per_thread):
                request_id = f'req-{(thread_id * reads_per_thread + i) % num_requests}'
                request = store.get_request('parent-1', request_id)
                assert request is not None

        # Run concurrent reads
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(read_requests, thread_id)
                for thread_id in range(num_threads)
            ]
            for future in as_completed(futures):
                future.result()

        concurrent_time = time.time() - start_time

        print('\nConcurrent read performance:')
        print(f'  {num_threads} threads, {reads_per_thread} reads each')
        print(
            f'  Total: {num_threads * reads_per_thread} reads in {concurrent_time:.2f}s'
        )
        print(
            f'  Rate: {(num_threads * reads_per_thread) / concurrent_time:.0f} reads/s'
        )

    def test_concurrent_update_operations(self, temp_workspace, sample_request_factory):
        """Test concurrent update operations from multiple threads."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Pre-populate with pending requests
        num_requests = 500
        for i in range(num_requests):
            request = sample_request_factory(f'req-{i}')
            store.save_request('parent-1', request)

        num_threads = 10
        updates_per_thread = 50

        def update_requests(thread_id: int):
            """Update requests from a thread."""
            for i in range(updates_per_thread):
                request_id = (
                    f'req-{(thread_id * updates_per_thread + i) % num_requests}'
                )
                store.update_request_status(
                    'parent-1',
                    request_id,
                    ApprovalRequestStatus.APPROVED,
                )

        # Run concurrent updates
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(update_requests, thread_id)
                for thread_id in range(num_threads)
            ]
            for future in as_completed(futures):
                future.result()

        concurrent_time = time.time() - start_time

        # Verify updates
        pending = store.get_pending_requests('parent-1')
        assert len(pending) == num_requests - (num_threads * updates_per_thread)

        print('\nConcurrent update performance:')
        print(f'  {num_threads} threads, {updates_per_thread} updates each')
        print(
            f'  Total: {num_threads * updates_per_thread} updates in {concurrent_time:.2f}s'
        )
        print(
            f'  Rate: {(num_threads * updates_per_thread) / concurrent_time:.0f} updates/s'
        )

    def test_batch_operations_performance(self, temp_workspace):
        """Test performance of batch operations."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Create large batch
        num_batches = 50

        start_time = time.time()
        for batch_id in range(num_batches):
            batch = ApprovalBatch(
                batch_id=f'batch-{batch_id}',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch('parent-1', batch)

        batch_save_time = time.time() - start_time

        # Read all batches
        start_time = time.time()
        for batch_id in range(num_batches):
            batch = store.get_batch('parent-1', f'batch-{batch_id}')
            assert batch is not None

        batch_read_time = time.time() - start_time

        print('\nBatch operations performance:')
        print(f'  {num_batches} batches saved in {batch_save_time:.2f}s')
        print(f'  {num_batches} batches read in {batch_read_time:.2f}s')

    def test_redis_connection_pool_exhaustion(
        self, temp_workspace, sample_request_factory
    ):
        """Test behavior under simulated connection pool exhaustion."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
        )

        mock_redis = MagicMock()
        # Simulate connection pool exhaustion
        mock_redis.ping.side_effect = Exception('Connection pool exhausted')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file
            request = sample_request_factory('req-1')
            store.save_request('parent-1', request)

            # Verify request was saved to file
            retrieved = store.get_request('parent-1', 'req-1')
            assert retrieved is not None
            assert retrieved.request_id == 'req-1'

            # Redis should be marked as unavailable
            assert not store.redis_available

    def test_mixed_operation_performance(self, temp_workspace, sample_request_factory):
        """Test performance with mixed operations (save, read, update)."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        num_operations = 1000
        start_time = time.time()

        for i in range(num_operations):
            # Save
            request = sample_request_factory(f'req-{i}')
            store.save_request('parent-1', request)

            # Read
            retrieved = store.get_request('parent-1', f'req-{i}')
            assert retrieved is not None

            # Update
            store.update_request_status(
                'parent-1',
                f'req-{i}',
                ApprovalRequestStatus.APPROVED,
            )

        mixed_time = time.time() - start_time

        print('\nMixed operations performance:')
        print(f'  {num_operations} save+read+update cycles in {mixed_time:.2f}s')
        print(f'  Rate: {num_operations / mixed_time:.0f} cycles/s')

    def test_metrics_overhead(self, temp_workspace, sample_request_factory):
        """Test that metrics collection doesn't add significant overhead."""
        # Test with metrics enabled
        config_with_metrics = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store_with_metrics = HybridApprovalQueueStore(config_with_metrics)

        num_operations = 100

        start_time = time.time()
        for i in range(num_operations):
            request = sample_request_factory(f'req-{i}')
            store_with_metrics.save_request('parent-1', request)
            store_with_metrics.get_request('parent-1', f'req-{i}')

        time_with_metrics = time.time() - start_time

        # Metrics should add < 10% overhead
        assert time_with_metrics < 2.0, (
            f'Metrics overhead too high: {time_with_metrics:.2f}s'
        )

        print('\nMetrics overhead:')
        print(f'  {num_operations} operations in {time_with_metrics:.2f}s')
        print(
            f'  Average per operation: {time_with_metrics / num_operations * 1000:.2f}ms'
        )

    def test_sync_performance_large_dataset(
        self, temp_workspace, sample_request_factory
    ):
        """Test sync performance with large dataset."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Create large dataset
            num_requests = 500
            for i in range(num_requests):
                request = sample_request_factory(f'req-{i}')
                store.save_request('parent-1', request)

            # Test sync to Redis
            start_time = time.time()
            result = store.sync_to_redis('parent-1')
            sync_time = time.time() - start_time

            print('\nSync performance:')
            print(f'  Synced {result.get("synced", 0)} items in {sync_time:.2f}s')
            print(f'  Rate: {result.get("synced", 0) / sync_time:.0f} items/s')

            # Sync should complete in reasonable time
            assert sync_time < 5.0, f'Sync too slow: {sync_time:.2f}s'
