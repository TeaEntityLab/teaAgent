"""Advanced feature tests for hybrid approval queue."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_hybrid_store import (
    HybridApprovalQueueConfig,
    HybridApprovalQueueStore,
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


class TestHybridApprovalQueueAdvanced:
    """Tests for advanced hybrid queue features."""

    def test_request_compression_enabled(self, temp_workspace, sample_request):
        """Test request compression for large payloads."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_compression=True,
            compression_threshold_bytes=100,
        )
        store = HybridApprovalQueueStore(config)

        # Create a large request
        large_request = SubagentApprovalRequest(
            request_id='req-large',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={
                'path': '/tmp/test.txt',
                'content': 'x' * 1000,  # Large content
            },
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_request('parent-1', large_request)

        # Retrieve and verify
        retrieved = store.get_request('parent-1', 'req-large')
        assert retrieved is not None
        assert retrieved.request_id == 'req-large'
        assert retrieved.tool_arguments['content'] == 'x' * 1000

    def test_request_compression_disabled(self, temp_workspace, sample_request):
        """Test that compression is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_compression=False,
        )
        store = HybridApprovalQueueStore(config)

        store.save_request('parent-1', sample_request)

        # Retrieve and verify
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None
        assert retrieved.request_id == 'req-123'

    def test_request_deduplication_enabled(self, temp_workspace, sample_request):
        """Test request deduplication prevents duplicates."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_deduplication=True,
            deduplication_window_seconds=300,
        )
        store = HybridApprovalQueueStore(config)

        # Save request first time
        store.save_request('parent-1', sample_request)

        # Try to save duplicate (same content, different ID)
        duplicate_request = SubagentApprovalRequest(
            request_id='req-456',  # Different ID
            subagent_id='subagent-1',  # Same subagent
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',  # Same tool
            tool_arguments={'path': '/tmp/test.txt', 'content': 'test'},  # Same args
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_request('parent-1', duplicate_request)

        # Only first request should exist
        pending = store.get_pending_requests('parent-1')
        assert len(pending) == 1
        assert pending[0].request_id == 'req-123'

    def test_request_deduplication_disabled(self, temp_workspace, sample_request):
        """Test that deduplication is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_deduplication=False,
        )
        store = HybridApprovalQueueStore(config)

        # Save request first time
        store.save_request('parent-1', sample_request)

        # Save duplicate with different ID
        duplicate_request = SubagentApprovalRequest(
            request_id='req-456',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_request('parent-1', duplicate_request)

        # Both requests should exist
        pending = store.get_pending_requests('parent-1')
        assert len(pending) == 2

    def test_ttl_expiration(self, temp_workspace, sample_request):
        """Test TTL auto-expiration of requests."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_ttl=True,
            default_ttl_seconds=1,  # 1 second TTL
        )
        store = HybridApprovalQueueStore(config)

        # Save request with TTL
        store.save_request('parent-1', sample_request)

        # Should be available immediately
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should be expired
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is None

    def test_ttl_disabled(self, temp_workspace, sample_request):
        """Test that TTL is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_ttl=False,
        )
        store = HybridApprovalQueueStore(config)

        store.save_request('parent-1', sample_request)

        # Wait longer than default TTL would be
        time.sleep(2)

        # Should still be available
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None

    def test_priority_queue_enabled(self, temp_workspace, sample_request):
        """Test priority queue support."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_priority=True,
        )
        store = HybridApprovalQueueStore(config)

        # Save multiple requests
        for i in range(5):
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

        # Set priorities
        store.set_request_priority('parent-1', 'req-0', 10)
        store.set_request_priority('parent-1', 'req-1', 5)
        store.set_request_priority('parent-1', 'req-2', 15)

        # Get pending requests by priority
        pending = store.get_pending_requests_by_priority('parent-1')

        # Should be sorted by priority (highest first)
        assert pending[0].request_id == 'req-2'  # priority 15
        assert pending[1].request_id == 'req-0'  # priority 10
        assert pending[2].request_id == 'req-1'  # priority 5

    def test_priority_queue_disabled(self, temp_workspace, sample_request):
        """Test that priority queue is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_priority=False,
        )
        store = HybridApprovalQueueStore(config)

        store.save_request('parent-1', sample_request)

        # Setting priority should fail
        result = store.set_request_priority('parent-1', 'req-123', 10)
        assert result is False

    def test_health_check_healthy(self, temp_workspace):
        """Test health check when all components are healthy."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_health_check=True,
        )
        store = HybridApprovalQueueStore(config)

        health = store.health_check()

        assert health['status'] == 'healthy'
        assert 'components' in health
        assert 'file' in health['components']
        assert health['components']['file']['status'] == 'ok'

    def test_health_check_degraded_redis(self, temp_workspace):
        """Test health check when Redis is unavailable."""
        from teaagent.subagents._approval_queue_redis_store import (
            RedisApprovalQueueConfig,
        )

        redis_config = RedisApprovalQueueConfig(host='localhost', port=6379)
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_config=redis_config,
            enable_health_check=True,
        )

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception('Redis unavailable')

        with patch(
            'teaagent.subagents._approval_queue_redis_store.redis.Redis',
            return_value=mock_redis,
        ):
            store = HybridApprovalQueueStore(config)
            health = store.health_check()

            assert health['status'] == 'degraded'
            assert health['components']['redis']['status'] == 'unavailable'

    def test_request_validation_valid(self, temp_workspace, sample_request):
        """Test validation of valid request."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        is_valid, errors = store.validate_request(sample_request)

        assert is_valid is True
        assert len(errors) == 0

    def test_request_validation_invalid(self, temp_workspace):
        """Test validation of invalid request."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Create invalid request
        invalid_request = SubagentApprovalRequest(
            request_id='',  # Empty ID
            subagent_id='',  # Empty subagent
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='',  # Empty tool
            tool_arguments='not a dict',  # Invalid type
            permission_mode='invalid-mode',  # Invalid mode
            isolation='invalid-isolation',  # Invalid isolation
            status=ApprovalRequestStatus.PENDING,
        )

        is_valid, errors = store.validate_request(invalid_request)

        assert is_valid is False
        assert len(errors) > 0
        assert any('request_id' in e for e in errors)
        assert any('subagent_id' in e for e in errors)
        assert any('tool_name' in e for e in errors)
        assert any('tool_arguments' in e for e in errors)
        assert any('permission_mode' in e for e in errors)
        assert any('isolation' in e for e in errors)

    def test_save_request_validation(self, temp_workspace):
        """Test that save_request validates before saving."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        invalid_request = SubagentApprovalRequest(
            request_id='',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        with pytest.raises(ValueError, match='Invalid request'):
            store.save_request('parent-1', invalid_request)

    def test_graceful_shutdown(self, temp_workspace, sample_request):
        """Test graceful shutdown."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save some data
        store.save_request('parent-1', sample_request)

        # Shutdown should not raise errors
        store.shutdown()

        # Verify data is still accessible after shutdown
        # (file store should still work)
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None

    def test_deduplication_window_cleanup(self, temp_workspace, sample_request):
        """Test that old deduplication hashes are cleaned up."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_deduplication=True,
            deduplication_window_seconds=1,  # 1 second window
        )
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Wait for window to expire
        time.sleep(1.1)

        # Try to save duplicate again (should succeed now)
        duplicate_request = SubagentApprovalRequest(
            request_id='req-456',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        store.save_request('parent-1', duplicate_request)

        # Both requests should exist now
        pending = store.get_pending_requests('parent-1')
        assert len(pending) == 2
