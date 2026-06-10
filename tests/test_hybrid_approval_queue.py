"""Unit tests for hybrid approval queue store."""

from __future__ import annotations

import json
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
from teaagent.subagents._approval_queue_store import ApprovalQueueStore
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


@pytest.fixture
def sample_batch():
    """Create a sample approval batch."""
    return ApprovalBatch(
        batch_id='batch-123',
        parent_run_id='parent-1',
        requests=[],
    )


class TestHybridApprovalQueueStore:
    """Test cases for HybridApprovalQueueStore."""

    def test_init_with_file_only(self, temp_workspace):
        """Test initialization with file store only."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        assert store.file_store is not None
        assert store.redis_store is None
        assert not store.redis_available

    def test_init_with_redis(self, temp_workspace):
        """Test initialization with Redis store."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        with patch('teaagent.subagents._approval_queue_redis_store.redis.Redis'):
            store = HybridApprovalQueueStore(config)

            assert store.file_store is not None
            assert store.redis_store is not None

    def test_save_request_file_only(self, temp_workspace, sample_request):
        """Test saving request with file store only."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Save request (should not raise exception)
        store.save_request('parent-1', sample_request)

        # Verify file store has the request
        snapshot = store.file_store.load('parent-1')
        assert 'req-123' in snapshot.requests

    def test_save_request_with_redis(self, temp_workspace, sample_request):
        """Test saving request with Redis store."""
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
            store.save_request('parent-1', sample_request)

            # Verify saved to Redis
            mock_redis.hset.assert_called()

            # Verify saved to file via hybrid store
            snapshot = store.file_store.load('parent-1')
            assert 'req-123' in snapshot.requests

    def test_get_request_from_file(self, temp_workspace, sample_request):
        """Test getting request from file store."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Save to file directly
        file_store = ApprovalQueueStore(temp_workspace)
        file_store.save('parent-1', {sample_request.request_id: sample_request}, {})

        # Get from hybrid store
        retrieved = store.get_request('parent-1', 'req-123')

        assert retrieved is not None
        assert retrieved.request_id == 'req-123'

    def test_update_request_status(self, temp_workspace, sample_request):
        """Test updating request status."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Update status
        result = store.update_request_status(
            'parent-1',
            'req-123',
            ApprovalRequestStatus.APPROVED,
            approved_by='test-user',
        )

        assert result is True

        # Verify updated
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved.status == ApprovalRequestStatus.APPROVED
        assert retrieved.approved_at is not None

    def test_get_pending_requests(self, temp_workspace):
        """Test getting pending requests."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Create pending requests
        for i in range(3):
            request = SubagentApprovalRequest(
                request_id=f'req-{i}',
                subagent_id='subagent-1',
                parent_run_id='parent-1',
                subagent_name='test-subagent',
                tool_name='write_file',
                tool_arguments={'path': f'/tmp/test{i}.txt', 'content': 'test'},
                permission_mode='workspace-write',
                isolation='shared',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_request('parent-1', request)

        # Get pending
        pending = store.get_pending_requests('parent-1')

        assert len(pending) == 3
        assert all(req.status == ApprovalRequestStatus.PENDING for req in pending)

    def test_save_batch(self, temp_workspace, sample_batch):
        """Test saving batch."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        store.save_batch('parent-1', sample_batch)

        # Verify saved to file
        file_store = ApprovalQueueStore(temp_workspace)
        snapshot = file_store.load('parent-1')
        assert 'batch-123' in snapshot.batches

    def test_get_batch(self, temp_workspace, sample_batch):
        """Test getting batch."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Save batch directly to file
        file_store = ApprovalQueueStore(temp_workspace)
        file_store.save('parent-1', {}, {sample_batch.batch_id: sample_batch})

        # Get from hybrid store
        retrieved = store.get_batch('parent-1', 'batch-123')

        assert retrieved is not None
        assert retrieved.batch_id == 'batch-123'

    def test_redis_fallback_on_write_failure(self, temp_workspace, sample_request):
        """Test fallback to file when Redis write fails."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            redis_primary=True,
            enable_fallback=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.hset.side_effect = Exception('Redis error')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Should not raise exception due to fallback
            store.save_request('parent-1', sample_request)

            # Verify saved to file
            file_store = ApprovalQueueStore(temp_workspace)
            snapshot = file_store.load('parent-1')
            assert 'req-123' in snapshot.requests

    def test_validate_consistency(self, temp_workspace):
        """Test consistency validation."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Add request to file
        request = SubagentApprovalRequest(
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
        store.save_request('parent-1', request)

        # Validate consistency
        consistency = store.validate_consistency('parent-1')

        assert consistency['file_requests'] == 1
        assert consistency['redis_requests'] == 0
        # When Redis is not available, consistency rate should be 1.0
        assert consistency['consistency_rate'] == 1.0
        assert consistency['redis_available'] is False

    def test_list_parent_run_ids(self, temp_workspace):
        """Test listing parent run IDs."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Create multiple parent runs
        for i in range(3):
            request = SubagentApprovalRequest(
                request_id=f'req-{i}',
                subagent_id='subagent-1',
                parent_run_id=f'parent-{i}',
                subagent_name='test-subagent',
                tool_name='write_file',
                tool_arguments={'path': f'/tmp/test{i}.txt', 'content': 'test'},
                permission_mode='workspace-write',
                isolation='shared',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_request(f'parent-{i}', request)

        # List parent runs
        parent_ids = store.list_parent_run_ids()

        assert len(parent_ids) == 3
        assert 'parent-0' in parent_ids
        assert 'parent-1' in parent_ids
        assert 'parent-2' in parent_ids

    def test_exists(self, temp_workspace, sample_request):
        """Test checking if parent run exists."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Initially should not exist
        assert not store.exists('parent-1')

        # Save request
        store.save_request('parent-1', sample_request)

        # Should exist now
        assert store.exists('parent-1')

    def test_delete_parent_run(self, temp_workspace, sample_request):
        """Test deleting parent run."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=None,
        )
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Verify exists
        assert store.exists('parent-1')

        # Delete
        result = store.delete_parent_run('parent-1')

        assert result is True
        assert not store.exists('parent-1')

    def test_sync_to_file(self, temp_workspace):
        """Test syncing Redis state to file."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = {'req-123'}
        mock_redis.hgetall.return_value = {
            'request_id': 'req-123',
            'subagent_id': 'subagent-1',
            'parent_run_id': 'parent-1',
            'subagent_name': 'test-subagent',
            'tool_name': 'write_file',
            'tool_arguments': json.dumps({'path': '/tmp/test.txt', 'content': 'test'}),
            'permission_mode': 'workspace-write',
            'isolation': 'shared',
            'status': 'pending',
        }

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Sync to file
            result = store.sync_to_file('parent-1')

            assert result['synced'] >= 0
            assert 'errors' in result

    def test_sync_to_redis(self, temp_workspace, sample_request):
        """Test syncing file state to Redis."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
        )

        # Save to file
        file_store = ApprovalQueueStore(temp_workspace)
        file_store.save('parent-1', {sample_request.request_id: sample_request}, {})

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Sync to Redis
            result = store.sync_to_redis('parent-1')

            assert result['synced'] >= 0
            assert 'errors' in result

    def test_circuit_breaker_enabled(self, temp_workspace):
        """Test that circuit breaker is enabled when configured."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=30,
        )
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            enable_circuit_breaker=True,
            circuit_breaker_config=circuit_breaker_config,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Circuit breaker should be initialized
            assert store._circuit_breaker is not None
            assert store._circuit_breaker.name == 'redis_approval_queue'
            assert store._circuit_breaker.config.failure_threshold == 3
            assert store._circuit_breaker.config.timeout_seconds == 30

    def test_circuit_breaker_disabled(self, temp_workspace):
        """Test that circuit breaker is disabled when configured."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            enable_circuit_breaker=False,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Circuit breaker should not be initialized
            assert store._circuit_breaker is None

    def test_metrics_collection(self, temp_workspace, sample_request):
        """Test that metrics are collected for operations."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Perform operations
        store.save_request('parent-1', sample_request)
        store.get_request('parent-1', sample_request.request_id)
        store.update_request_status(
            'parent-1',
            sample_request.request_id,
            ApprovalRequestStatus.APPROVED,
        )

        # Get metrics
        metrics = store.get_metrics()

        assert metrics is not None
        assert 'backend_type' in metrics
        assert 'operation_metrics' in metrics
        assert 'request_metrics' in metrics
        assert 'uptime_seconds' in metrics

        # Check operation metrics
        assert 'save_request' in metrics['operation_metrics']
        assert 'get_request' in metrics['operation_metrics']
        assert 'update_request_status' in metrics['operation_metrics']

        # Check counts
        assert metrics['operation_metrics']['save_request']['count'] >= 1
        assert metrics['operation_metrics']['get_request']['count'] >= 1
        assert metrics['operation_metrics']['update_request_status']['count'] >= 1

    def test_dynamic_sync_interval_disabled(self, temp_workspace):
        """Test that dynamic sync interval is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_dynamic_sync=False,
            sync_interval_seconds=60,
        )
        store = HybridApprovalQueueStore(config)

        # Should return fixed interval
        interval = store._calculate_dynamic_sync_interval()
        assert interval == 60

    def test_dynamic_sync_interval_enabled(self, temp_workspace, sample_request):
        """Test that dynamic sync interval adjusts based on load."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_dynamic_sync=True,
            sync_interval_seconds=60,
            min_sync_interval_seconds=10,
            max_sync_interval_seconds=300,
        )
        store = HybridApprovalQueueStore(config)

        # Perform some operations to generate metrics
        for _ in range(10):
            store.save_request('parent-1', sample_request)

        # Calculate dynamic interval
        interval = store._calculate_dynamic_sync_interval()

        # Should be within bounds
        assert 10 <= interval <= 300

    def test_should_sync(self, temp_workspace):
        """Test sync timing logic."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            sync_interval_seconds=60,
        )
        store = HybridApprovalQueueStore(config)

        # First call should return True (no previous sync)
        assert store.should_sync() is True

        # Record sync
        store.record_sync()

        # Immediate call should return False
        assert store.should_sync() is False

    def test_cleanup_orphaned_requests(self, temp_workspace, sample_request):
        """Test cleanup of orphaned requests."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save a request
        store.save_request('parent-1', sample_request)

        # Mark as approved
        store.update_request_status(
            'parent-1',
            sample_request.request_id,
            ApprovalRequestStatus.APPROVED,
        )

        # Run cleanup with very short max_age
        cleanup_report = store.cleanup_orphaned_requests(
            max_age_seconds=0,
            timeout_seconds=180,
        )

        assert 'timed_out_requests' in cleanup_report
        assert 'expired_resolved_requests' in cleanup_report
        assert 'orphaned_parent_runs' in cleanup_report
        assert 'errors' in cleanup_report

    def test_get_circuit_breaker_stats(self, temp_workspace):
        """Test getting circuit breaker statistics."""
        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            enable_circuit_breaker=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)

            # Get stats
            stats = store.get_circuit_breaker_stats()

            assert stats is not None
            assert 'name' in stats
            assert 'state' in stats
            assert 'failures' in stats
            assert 'successes' in stats

    def test_circuit_breaker_stats_disabled(self, temp_workspace):
        """Test circuit breaker stats when disabled."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_circuit_breaker=False,
        )
        store = HybridApprovalQueueStore(config)

        # Should return None
        stats = store.get_circuit_breaker_stats()
        assert stats is None
