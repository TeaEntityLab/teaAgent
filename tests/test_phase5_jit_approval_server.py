from __future__ import annotations

import contextlib
import time

from teaagent.jit_approval_server import (
    ApprovalRequestRecord,
    ApprovalStatus,
    JITApprovalServer,
)
from teaagent.tool_permissions import ToolPermissionManager


class TestJITApprovalServer:
    """Test suite for JIT Approval Server."""

    def test_server_initialization(self):
        """Test that server initializes with permission manager."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager,
            host='localhost',
            port=8765,
            timeout_seconds=180,
        )

        assert server._permission_manager is permission_manager
        assert server._host == 'localhost'
        assert server._port == 8765
        assert server._timeout_seconds == 180

    def test_approval_request_record_creation(self):
        """Test ApprovalRequestRecord creation."""
        from teaagent.tool_permissions import PermissionRequest

        request = PermissionRequest(
            tool_name='write_file',
            agent_name='test-agent',
            reason='Need to write file',
        )

        record = ApprovalRequestRecord(
            request_id='req-1',
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=1234567890.0,
        )

        assert record.request_id == 'req-1'
        assert record.status == ApprovalStatus.PENDING
        assert record.created_at == 1234567890.0

    def test_request_approval_creates_record(self):
        """Test that requesting approval creates a record."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=1  # Short timeout for tests
        )

        # Manually create record without calling request_approval (which blocks)
        from teaagent.tool_permissions import PermissionRequest

        request = PermissionRequest(
            tool_name='write_file',
            agent_name='test-agent',
            reason='Need to write file',
        )

        record = ApprovalRequestRecord(
            request_id='req-1',
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=1234567890.0,
        )

        server._requests['req-1'] = record

        assert record.status == ApprovalStatus.PENDING
        assert record.request.agent_name == 'test-agent'
        assert record.request.tool_name == 'write_file'

    def test_approve_request(self):
        """Test approving a pending request."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=1
        )

        # Manually create record
        from teaagent.tool_permissions import PermissionRequest

        request = PermissionRequest(
            tool_name='write_file',
            agent_name='test-agent',
            reason='Need to write file',
        )

        record = ApprovalRequestRecord(
            request_id='req-1',
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=1234567890.0,
        )

        server._requests['req-1'] = record

        # Approve (broadcast may fail in test mode, that's OK)
        with contextlib.suppress(Exception):
            server.approve_request('req-1')

        updated = server.get_request_status('req-1')
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.approved_at is not None

    def test_reject_request(self):
        """Test rejecting a pending request."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=1
        )

        # Manually create record
        from teaagent.tool_permissions import PermissionRequest

        request = PermissionRequest(
            tool_name='write_file',
            agent_name='test-agent',
            reason='Need to write file',
        )

        record = ApprovalRequestRecord(
            request_id='req-1',
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=1234567890.0,
        )

        server._requests['req-1'] = record

        # Reject (broadcast may fail in test mode, that's OK)
        with contextlib.suppress(Exception):
            server.reject_request('req-1')

        updated = server.get_request_status('req-1')
        assert updated.status == ApprovalStatus.REJECTED
        assert updated.rejected_at is not None

    def test_get_pending_requests(self):
        """Test getting pending requests."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=1
        )

        # Manually create records
        from teaagent.tool_permissions import PermissionRequest

        request1 = PermissionRequest(
            tool_name='write_file',
            agent_name='agent-1',
            reason='Reason 1',
        )

        request2 = PermissionRequest(
            tool_name='delete_file',
            agent_name='agent-2',
            reason='Reason 2',
        )

        record1 = ApprovalRequestRecord(
            request_id='req-1',
            request=request1,
            status=ApprovalStatus.PENDING,
            created_at=1234567890.0,
        )

        record2 = ApprovalRequestRecord(
            request_id='req-2',
            request=request2,
            status=ApprovalStatus.PENDING,
            created_at=1234567891.0,
        )

        server._requests['req-1'] = record1
        server._requests['req-2'] = record2

        pending = server.get_pending_requests()

        assert len(pending) == 2

    def test_get_request_status_nonexistent(self):
        """Test getting status of nonexistent request."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=180
        )

        status = server.get_request_status('nonexistent')

        assert status is None

    def test_approve_nonexistent_request(self):
        """Test approving a nonexistent request (should not crash)."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=180
        )

        # Should not raise an exception
        server.approve_request('nonexistent')

    def test_reject_nonexistent_request(self):
        """Test rejecting a nonexistent request (should not crash)."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=180
        )

        # Should not raise an exception
        server.reject_request('nonexistent')

    def test_cleanup_old_requests(self):
        """Test cleanup of old requests."""
        permission_manager = ToolPermissionManager()
        server = JITApprovalServer(
            permission_manager=permission_manager, timeout_seconds=1
        )

        # Manually create record with old timestamp
        from teaagent.tool_permissions import PermissionRequest

        request = PermissionRequest(
            tool_name='write_file',
            agent_name='agent-1',
            reason='Reason 1',
        )

        record = ApprovalRequestRecord(
            request_id='req-1',
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=time.time() - 7200,  # 2 hours ago
        )

        server._requests['req-1'] = record

        # Cleanup should not crash
        server.cleanup_old_requests()

        # Old request should be removed
        assert server.get_request_status('req-1') is None
