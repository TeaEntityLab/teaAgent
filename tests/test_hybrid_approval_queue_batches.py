"""Batch-specific tests for hybrid approval queue."""

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


class TestHybridApprovalQueueBatches:
    """Batch-specific tests for hybrid approval queue."""

    def test_batch_creation_and_retrieval(self, temp_workspace):
        """Test creating and retrieving batches."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_batch('parent-1', batch)

        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved is not None
        assert retrieved.batch_id == 'batch-1'
        assert retrieved.parent_run_id == 'parent-1'
        assert retrieved.status == ApprovalRequestStatus.PENDING

    def test_batch_status_update(self, temp_workspace):
        """Test updating batch status."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_batch('parent-1', batch)

        # Update batch status by recreating with new status
        updated_batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.APPROVED,
        )

        store.save_batch('parent-1', updated_batch)

        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved.status == ApprovalRequestStatus.APPROVED

    def test_multiple_batches_same_parent(self, temp_workspace):
        """Test multiple batches for the same parent run."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Create multiple batches
        for i in range(5):
            batch = ApprovalBatch(
                batch_id=f'batch-{i}',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch('parent-1', batch)

        # Retrieve all batches
        for i in range(5):
            batch = store.get_batch('parent-1', f'batch-{i}')
            assert batch is not None
            assert batch.batch_id == f'batch-{i}'

    def test_batch_with_redis_fallback(self, temp_workspace):
        """Test batch operations with Redis fallback."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

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

            # Save to both backends
            store.save_batch('parent-1', batch)

            # Retrieve from file (primary for reads)
            retrieved = store.get_batch('parent-1', 'batch-1')
            assert retrieved is not None
            assert retrieved.batch_id == 'batch-1'

    def test_batch_redis_write_failure_fallback(self, temp_workspace):
        """Test batch save with Redis write failure fallback."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.hset.side_effect = Exception('Redis write failed')

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

    def test_batch_deletion(self, temp_workspace):
        """Test deleting batches."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_batch('parent-1', batch)

        # Delete parent run (should delete batches too)
        store.delete_parent_run('parent-1')

        # Verify batch is gone
        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved is None

    def test_batch_sync_to_file(self, temp_workspace):
        """Test syncing batches from Redis to file."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = {b'batch-1'}
        mock_redis.hgetall.return_value = {
            b'batch_id': b'batch-1',
            b'parent_run_id': b'parent-1',
            b'created_at': b'2026-06-10T00:00:00',
            b'status': b'pending',
        }

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Sync to file
            result = store.sync_to_file('parent-1')

            assert 'synced' in result
            assert 'errors' in result

    def test_batch_sync_to_redis(self, temp_workspace):
        """Test syncing batches from file to Redis."""
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

            # Create batch in file
            batch = ApprovalBatch(
                batch_id='batch-1',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch('parent-1', batch)

            # Sync to Redis
            result = store.sync_to_redis('parent-1')

            assert 'synced' in result
            assert result['synced'] >= 1

    def test_batch_consistency_validation(self, temp_workspace):
        """Test consistency validation for batches."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = {b'batch-1'}

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Create batch in file
            batch = ApprovalBatch(
                batch_id='batch-1',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch('parent-1', batch)

            # Validate consistency
            report = store.validate_consistency('parent-1')

            assert 'file_batches' in report
            assert 'redis_batches' in report
            assert 'consistency_rate' in report

    def test_batch_with_requests(self, temp_workspace, sample_request):
        """Test batches that contain requests."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Create batch
        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.PENDING,
        )
        store.save_batch('parent-1', batch)

        # Verify both exist
        retrieved_request = store.get_request('parent-1', 'req-123')
        assert retrieved_request is not None

        retrieved_batch = store.get_batch('parent-1', 'batch-1')
        assert retrieved_batch is not None

    def test_batch_denied_status(self, temp_workspace):
        """Test batch with denied status."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.DENIED,
        )

        store.save_batch('parent-1', batch)

        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved.status == ApprovalRequestStatus.DENIED

    def test_batch_timeout_status(self, temp_workspace):
        """Test batch with timeout status."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.TIMEOUT,
        )

        store.save_batch('parent-1', batch)

        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved.status == ApprovalRequestStatus.TIMEOUT

    def test_batch_cancelled_status(self, temp_workspace):
        """Test batch with cancelled status."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.CANCELLED,
        )

        store.save_batch('parent-1', batch)

        retrieved = store.get_batch('parent-1', 'batch-1')
        assert retrieved.status == ApprovalRequestStatus.CANCELLED

    def test_batch_exists_check(self, temp_workspace):
        """Test checking if batch exists."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Batch doesn't exist yet
        batch = store.get_batch('parent-1', 'batch-1')
        assert batch is None

        # Create batch
        batch = ApprovalBatch(
            batch_id='batch-1',
            parent_run_id='parent-1',
            created_at='2026-06-10T00:00:00',
            status=ApprovalRequestStatus.PENDING,
        )
        store.save_batch('parent-1', batch)

        # Batch exists now
        batch = store.get_batch('parent-1', 'batch-1')
        assert batch is not None

    def test_batch_different_parent_runs(self, temp_workspace):
        """Test batches for different parent runs."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Create batches for different parent runs
        for parent_id in ['parent-1', 'parent-2', 'parent-3']:
            batch = ApprovalBatch(
                batch_id=f'batch-{parent_id}',
                parent_run_id=parent_id,
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch(parent_id, batch)

        # Verify each batch is in its parent run
        for parent_id in ['parent-1', 'parent-2', 'parent-3']:
            batch = store.get_batch(parent_id, f'batch-{parent_id}')
            assert batch is not None
            assert batch.parent_run_id == parent_id

    def test_batch_large_scale(self, temp_workspace):
        """Test large number of batches."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        num_batches = 100

        # Create many batches
        for i in range(num_batches):
            batch = ApprovalBatch(
                batch_id=f'batch-{i}',
                parent_run_id='parent-1',
                created_at='2026-06-10T00:00:00',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_batch('parent-1', batch)

        # Verify all batches
        for i in range(num_batches):
            batch = store.get_batch('parent-1', f'batch-{i}')
            assert batch is not None
            assert batch.batch_id == f'batch-{i}'
