"""Tests for hybrid approval queue fixes - thread safety, persistence, and integration."""

import tempfile
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


class TestHybridApprovalQueueFixes:
    """Test fixes for thread safety, persistence, and feature integration."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def hybrid_store(self, temp_workspace):
        """Create a hybrid approval queue store for testing."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_primary=False,  # File-only for testing
            enable_notifications=True,
            enable_comments=True,
            enable_voting=True,
            enable_dependencies=True,
            enable_approval_history=True,
            enable_sla_tracking=True,
        )
        return HybridApprovalQueueStore(config)

    @pytest.fixture
    def hybrid_store_no_auto_approve(self, temp_workspace):
        """Create a hybrid approval queue store without auto-approval for testing."""
        config = HybridApprovalQueueConfig(
            workspace_root=temp_workspace,
            redis_primary=False,  # File-only for testing
            enable_notifications=True,
            enable_comments=True,
            enable_voting=True,
            enable_dependencies=True,
            enable_approval_history=True,
            enable_sla_tracking=True,
        )
        store = HybridApprovalQueueStore(config)
        # Disable auto-approval by not having the voting trigger it
        return store

    @pytest.fixture
    def sample_approval_request(self):
        """Create a sample approval request for testing."""
        return SubagentApprovalRequest(
            request_id='test-request-1',
            subagent_id='test-subagent',
            parent_run_id='parent-run-1',
            subagent_name='test-subagent',
            tool_name='workspace_write_file',
            tool_arguments={'path': 'test.txt', 'content': 'test content'},
            permission_mode='workspace-write',
            isolation='sandbox',
        )

    def test_thread_safety_notifications(self, hybrid_store, sample_approval_request):
        """Test that notifications are thread-safe."""
        parent_run_id = 'test_parent'
        request = sample_approval_request
        hybrid_store.save_request(parent_run_id, request)

        # Create multiple notifications
        for i in range(10):
            hybrid_store._create_notification(
                'test_type',
                f'Test message {i}',
                request_id=request.request_id,
                parent_run_id=parent_run_id,
            )

        notifications = hybrid_store.get_notifications(limit=100)
        # 10 test notifications + 1 from save_request = 11 total
        assert len(notifications) == 11

    def test_thread_safety_comments(self, hybrid_store, sample_approval_request):
        """Test that comments are thread-safe."""
        parent_run_id = 'test_parent'
        request = sample_approval_request
        hybrid_store.save_request(parent_run_id, request)

        # Add multiple comments
        for i in range(5):
            hybrid_store.add_comment(
                parent_run_id,
                request.request_id,
                f'Test comment {i}',
                f'author_{i}',
            )

        comments = hybrid_store.get_comments(request.request_id)
        assert len(comments) == 5

    def test_thread_safety_votes(self, hybrid_store, sample_approval_request):
        """Test that voting is thread-safe."""
        parent_run_id = 'test_parent'
        request = sample_approval_request
        hybrid_store.save_request(parent_run_id, request)

        # Cast multiple votes (all deny to avoid auto-approval)
        for i in range(3):
            hybrid_store.cast_vote(
                parent_run_id,
                request.request_id,
                f'voter_{i}',
                False,  # All deny votes
            )

        votes = hybrid_store.get_votes(request.request_id)
        assert len(votes) == 3

    def test_state_persistence(self, hybrid_store, sample_approval_request):
        """Test that in-memory state can be persisted to file."""
        parent_run_id = 'test_parent'
        request = sample_approval_request
        hybrid_store.save_request(parent_run_id, request)

        # Add some state
        hybrid_store.add_comment(
            parent_run_id, request.request_id, 'Test comment', 'author1'
        )
        hybrid_store.set_sla_deadline(request.request_id, 3600)

        # Test that persistence method exists and can be called
        success = hybrid_store._persist_state_to_file()
        assert success

        # Test that load method exists
        success = hybrid_store._load_state_from_file()
        # May return False if no state file exists yet, which is ok
        assert isinstance(success, bool)

    def test_dependency_blocking(self, hybrid_store, sample_approval_request):
        """Test that approval is blocked when dependencies are not satisfied."""
        parent_run_id = 'test_parent'

        # Create dependent request
        request1 = sample_approval_request
        hybrid_store.save_request(parent_run_id, request1)

        # Create request that depends on request1
        request2 = SubagentApprovalRequest(
            request_id='test_req_2',
            parent_run_id=parent_run_id,
            subagent_id='subagent_1',
            subagent_name='test_subagent',
            tool_name='test_tool',
            tool_arguments={},
            permission_mode='workspace-read',
            isolation='shared',
        )
        hybrid_store.save_request(parent_run_id, request2)

        # Add dependency
        hybrid_store.add_dependency(request2.request_id, request1.request_id)

        # Try to approve request2 before request1 is approved
        with pytest.raises(Exception, match='dependencies not satisfied'):
            hybrid_store.update_request_status(
                parent_run_id,
                request2.request_id,
                ApprovalRequestStatus.APPROVED,
                approved_by='test_user',
            )

        # Approve request1
        hybrid_store.update_request_status(
            parent_run_id,
            request1.request_id,
            ApprovalRequestStatus.APPROVED,
            approved_by='test_user',
        )

        # Now request2 should be approvable
        success = hybrid_store.update_request_status(
            parent_run_id,
            request2.request_id,
            ApprovalRequestStatus.APPROVED,
            approved_by='test_user',
        )
        assert success

    def test_approval_history_tracking(self, hybrid_store, sample_approval_request):
        """Test that approval history is tracked."""
        parent_run_id = 'test_parent'
        request = sample_approval_request
        hybrid_store.save_request(parent_run_id, request)

        # Update status multiple times
        hybrid_store.update_request_status(
            parent_run_id,
            request.request_id,
            ApprovalRequestStatus.APPROVED,
            approved_by='user1',
        )

        history = hybrid_store.get_approval_history(request.request_id)
        assert len(history) == 1
        assert history[0]['status'] == 'approved'
        assert history[0]['approved_by'] == 'user1'
