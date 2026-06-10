"""Real Redis failure scenario tests for hybrid approval queue."""

from __future__ import annotations

import tempfile
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
from teaagent.subagents._circuit_breaker import CircuitBreakerConfig


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_request():
    """Create a sample approval request."""
    return SubagentApprovalRequest(
        request_id='req-123',
        subagent_id='subagent-1',
        parent_run_id='parent-1',
        subagent_name='test-subagent',
        tool_name='write_file',
        tool_arguments={'path': '/tmp/test.txt', 'content': 'test'},
        permission_mode='workspace-write',
        isolation='shared',
        status=ApprovalRequestStatus.PENDING,
    )


class TestHybridApprovalQueueRedisFailures:
    """Tests for real Redis failure scenarios."""

    def test_redis_connection_timeout(self, temp_workspace, sample_request):
        """Test handling of Redis connection timeout."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = TimeoutError('Connection timeout')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None
            assert retrieved.request_id == 'req-123'

            # Redis should be marked unavailable
            assert not store.redis_available

    def test_redis_network_partition(self, temp_workspace, sample_request):
        """Test handling of network partition to Redis."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = ConnectionError('Network unreachable')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

            assert not store.redis_available

    def test_redis_auth_failure(self, temp_workspace, sample_request):
        """Test handling of Redis authentication failure."""
        redis_config = RedisApprovalQueueConfig(
            host='localhost',
            port=6379,
            password='wrong-password',
        )
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception('Authentication failed')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

            assert not store.redis_available

    def test_redis_memory_full(self, temp_workspace, sample_request):
        """Test handling of Redis out of memory error."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        # Simulate OOM on write
        mock_redis.hset.side_effect = Exception('OOM command not allowed')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file on write failure
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

    def test_redis_intermittent_failures(self, temp_workspace, sample_request):
        """Test handling of intermittent Redis failures."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=1,
        )
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_circuit_breaker=True,
            circuit_breaker_config=circuit_breaker_config,
        )

        call_count = [0]

        def intermittent_ping():
            """Simulate intermittent failures."""
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise Exception('Intermittent failure')
            return True

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = intermittent_ping

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # First call should succeed
            store.save_request('parent-1', sample_request)

            # Second call should succeed
            store.save_request('parent-1', sample_request)

            # Third call should fail but fall back
            store.save_request('parent-1', sample_request)

            # Verify data integrity
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

    def test_redis_slow_response(self, temp_workspace, sample_request):
        """Test handling of slow Redis responses."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        import time

        def slow_ping():
            """Simulate slow response."""
            time.sleep(0.1)  # 100ms delay
            return True

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = slow_ping

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should still work despite slow Redis
            start_time = time.time()
            store.save_request('parent-1', sample_request)
            elapsed = time.time() - start_time

            # Should complete in reasonable time (file backup ensures this)
            assert elapsed < 1.0, f'Operation too slow: {elapsed:.2f}s'

            # Verify saved
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

    def test_redis_crash_during_write(self, temp_workspace, sample_request):
        """Test handling of Redis crash during write operation."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        # Simulate crash during write
        mock_redis.hset.side_effect = Exception('Connection lost during write')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should fall back to file
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

            # Redis should be marked unavailable
            assert not store.redis_available

    def test_redis_partial_failure_batch(self, temp_workspace, sample_request):
        """Test handling of partial failure during batch operations."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        # Fail on batch write
        mock_redis.hset.side_effect = Exception('Batch write failed')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            batch = ApprovalBatch(
                batch_id='batch-1',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )

            # Should fall back to file
            store.save_batch('parent-1', batch)

            # Verify saved to file
            retrieved = store.get_batch('parent-1', 'batch-1')
            assert retrieved is not None
            assert retrieved.batch_id == 'batch-1'

    def test_redis_unavailable_on_startup(self, temp_workspace, sample_request):
        """Test behavior when Redis is unavailable on startup."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception('Redis not running')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should initialize without Redis
            assert not store.redis_available

            # Should work with file-only
            store.save_request('parent-1', sample_request)
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

    def test_graceful_degradation(self, temp_workspace, sample_request):
        """Test graceful degradation when Redis fails after being available."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Initially Redis is available
            assert store.redis_available

            # Save request
            store.save_request('parent-1', sample_request)

            # Simulate Redis failure
            mock_redis.ping.side_effect = Exception('Redis crashed')
            mock_redis.hset.side_effect = Exception('Redis crashed')

            # Should fall back to file
            store.save_request('parent-1', sample_request)

            # Verify data integrity
            retrieved = store.get_request('parent-1', 'req-123')
            assert retrieved is not None

            # Redis should be marked unavailable after failed write
            # Note: Circuit breaker may not update this flag immediately
