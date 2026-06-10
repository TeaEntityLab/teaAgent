"""Extended feature tests for hybrid approval queue."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

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


class TestHybridApprovalQueueExtended:
    """Tests for extended hybrid queue features."""

    def test_rate_limiting_enabled(self, temp_workspace, sample_request):
        """Test rate limiting per subagent."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_rate_limiting=True,
            rate_limit_requests_per_minute=5,
        )
        store = HybridApprovalQueueStore(config)

        # Save 5 requests (at limit)
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

        # 6th request should be rate limited
        request_6 = SubagentApprovalRequest(
            request_id='req-6',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test6.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )

        with pytest.raises(Exception, match='Rate limit exceeded'):
            store.save_request('parent-1', request_6)

    def test_rate_limiting_disabled(self, temp_workspace, sample_request):
        """Test that rate limiting is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_rate_limiting=False,
        )
        store = HybridApprovalQueueStore(config)

        # Should be able to save many requests
        for i in range(20):
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

        pending = store.get_pending_requests('parent-1')
        assert len(pending) == 20

    def test_request_cancellation(self, temp_workspace, sample_request):
        """Test request cancellation."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Cancel request
        result = store.cancel_request('parent-1', 'req-123', 'User cancelled')

        assert result is True

        # Verify status is cancelled
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None
        assert retrieved.status == ApprovalRequestStatus.CANCELLED

    def test_cancel_non_pending_request(self, temp_workspace, sample_request):
        """Test cancelling a non-pending request."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save and approve request
        store.save_request('parent-1', sample_request)
        store.update_request_status(
            'parent-1', 'req-123', ApprovalRequestStatus.APPROVED
        )

        # Try to cancel (should fail)
        result = store.cancel_request('parent-1', 'req-123', 'Test')

        assert result is False

    def test_search_requests_by_subagent(self, temp_workspace, sample_request):
        """Test searching requests by subagent."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save requests from different subagents
        for i in range(3):
            request = SubagentApprovalRequest(
                request_id=f'req-{i}',
                subagent_id=f'subagent-{i % 2}',  # subagent-0, subagent-1
                parent_run_id='parent-1',
                subagent_name='test-subagent',
                tool_name='write_file',
                tool_arguments={'path': f'/tmp/test{i}.txt', 'content': 'test'},
                permission_mode='workspace-write',
                isolation='shared',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_request('parent-1', request)

        # Search for subagent-0
        results = store.search_requests('parent-1', subagent_id='subagent-0')

        assert len(results) == 2
        assert all(r.subagent_id == 'subagent-0' for r in results)

    def test_search_requests_by_tool(self, temp_workspace, sample_request):
        """Test searching requests by tool name."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save requests with different tools
        for i in range(3):
            request = SubagentApprovalRequest(
                request_id=f'req-{i}',
                subagent_id='subagent-1',
                parent_run_id='parent-1',
                subagent_name='test-subagent',
                tool_name=f'tool_{i % 2}',  # tool_0, tool_1
                tool_arguments={'path': f'/tmp/test{i}.txt', 'content': 'test'},
                permission_mode='workspace-write',
                isolation='shared',
                status=ApprovalRequestStatus.PENDING,
            )
            store.save_request('parent-1', request)

        # Search for tool_0
        results = store.search_requests('parent-1', tool_name='tool_0')

        assert len(results) == 2
        assert all(r.tool_name == 'tool_0' for r in results)

    def test_search_requests_by_status(self, temp_workspace, sample_request):
        """Test searching requests by status."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save requests
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

        # Approve one request
        store.update_request_status('parent-1', 'req-0', ApprovalRequestStatus.APPROVED)

        # Search for pending requests
        results = store.search_requests('parent-1', status='pending')

        assert len(results) == 2
        assert all(r.status == ApprovalRequestStatus.PENDING for r in results)

    def test_export_requests(self, temp_workspace, sample_request):
        """Test exporting requests."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Export
        exported = store.export_requests('parent-1', format='json')

        assert 'parent_run_id' in exported
        assert 'requests' in exported
        assert 'req-123' in exported  # Check in JSON string

    def test_import_requests(self, temp_workspace, sample_request):
        """Test importing requests."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Export from one parent run
        store.save_request('parent-1', sample_request)
        exported = store.export_requests('parent-1', format='json')

        # Import to another parent run
        imported_count = store.import_requests('parent-2', exported, format='json')

        assert imported_count == 1

        # Verify import
        retrieved = store.get_request('parent-2', 'req-123')
        assert retrieved is not None

    def test_audit_trail(self, temp_workspace, sample_request):
        """Test audit trail functionality."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_audit_trail=True,
        )
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Get audit trail
        audit = store.get_audit_trail(parent_run_id='parent-1')

        assert len(audit) > 0
        assert audit[0]['action'] == 'save_request'
        assert audit[0]['request_id'] == 'req-123'

    def test_audit_trail_filtered(self, temp_workspace, sample_request):
        """Test filtering audit trail by request ID."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_audit_trail=True,
        )
        store = HybridApprovalQueueStore(config)

        # Save multiple requests
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

        # Get audit trail for specific request
        audit = store.get_audit_trail(parent_run_id='parent-1', request_id='req-1')

        assert len(audit) == 1
        assert audit[0]['request_id'] == 'req-1'

    def test_archive_old_requests(self, temp_workspace, sample_request):
        """Test archival of old requests."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_archival=True,
            archival_age_days=0,  # Archive immediately
        )
        store = HybridApprovalQueueStore(config)

        # Save request
        store.save_request('parent-1', sample_request)

        # Wait a moment to ensure age
        time.sleep(0.1)

        # Archive
        report = store.archive_old_requests(max_age_days=0)

        assert report['archived'] >= 1
        assert len(report['archived_requests']) > 0

    def test_archival_disabled(self, temp_workspace, sample_request):
        """Test that archival is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_archival=False,
        )
        store = HybridApprovalQueueStore(config)

        store.save_request('parent-1', sample_request)

        # Archival should return 0
        report = store.archive_old_requests()

        assert report['archived'] == 0

    def test_combined_search_filters(self, temp_workspace, sample_request):
        """Test combining multiple search filters."""
        config = HybridApprovalQueueConfig(workspace_root=temp_workspace)
        store = HybridApprovalQueueStore(config)

        # Save requests with different attributes
        request1 = SubagentApprovalRequest(
            request_id='req-1',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test1.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )
        request2 = SubagentApprovalRequest(
            request_id='req-2',
            subagent_id='subagent-2',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='read_file',
            tool_arguments={'path': '/tmp/test2.txt'},
            permission_mode='workspace-read',
            isolation='shared',
            status=ApprovalRequestStatus.PENDING,
        )
        request3 = SubagentApprovalRequest(
            request_id='req-3',
            subagent_id='subagent-1',
            parent_run_id='parent-1',
            subagent_name='test-subagent',
            tool_name='write_file',
            tool_arguments={'path': '/tmp/test3.txt', 'content': 'test'},
            permission_mode='workspace-write',
            isolation='shared',
            status=ApprovalRequestStatus.APPROVED,
        )

        store.save_request('parent-1', request1)
        store.save_request('parent-1', request2)
        store.save_request('parent-1', request3)

        # Search with multiple filters
        results = store.search_requests(
            'parent-1',
            subagent_id='subagent-1',
            tool_name='write_file',
            status='pending',
        )

        assert len(results) == 1
        assert results[0].request_id == 'req-1'

    def test_encryption_enabled(self, temp_workspace, sample_request):
        """Test request encryption for sensitive data."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_encryption=True,
        )
        store = HybridApprovalQueueStore(config)

        # Save request with encryption
        store.save_request('parent-1', sample_request)

        # Retrieve and verify
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None
        assert retrieved.request_id == 'req-123'
        assert retrieved.tool_arguments == sample_request.tool_arguments

    def test_encryption_disabled(self, temp_workspace, sample_request):
        """Test that encryption is disabled when configured."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            enable_encryption=False,
        )
        store = HybridApprovalQueueStore(config)

        store.save_request('parent-1', sample_request)

        # Retrieve and verify
        retrieved = store.get_request('parent-1', 'req-123')
        assert retrieved is not None
        assert retrieved.request_id == 'req-123'
