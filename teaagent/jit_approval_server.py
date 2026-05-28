"""Remote JIT Approval Server - SSE for tool permission requests.

This module implements the Cooragent remote JIT approval server that:
1. Broadcasts JIT tool permission requests via SSE
2. Provides web interface for approval/rejection
3. Implements 3-minute timeout with safe abort
4. Integrates with ToolPermissionManager for approval flow
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from teaagent.tool_permissions import PermissionRequest, ToolPermissionManager

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval request status."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    TIMEOUT = 'timeout'


@dataclass
class ApprovalRequestRecord:
    """Record of an approval request."""

    request_id: str
    request: PermissionRequest
    status: ApprovalStatus
    created_at: float
    timeout_seconds: int = 180
    approved_at: Optional[float] = None
    rejected_at: Optional[float] = None


class JITApprovalServer:
    """SSE server for remote JIT tool approval."""

    def __init__(
        self,
        permission_manager: ToolPermissionManager,
        host: str = 'localhost',
        port: int = 8765,
        timeout_seconds: int = 180,
    ) -> None:
        self._permission_manager = permission_manager
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._requests: dict[str, ApprovalRequestRecord] = {}
        self._server: Optional[asyncio.Server] = None
        self._clients: set[asyncio.Queue] = set()

    async def start(self) -> None:
        """Start the SSE server."""
        self._server = await asyncio.start_server(
            self._host, self._port, self._handle_connection
        )
        logger.info(f'JIT Approval Server started on {self._host}:{self._port}')

    async def stop(self) -> None:
        """Stop the SSE server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info('JIT Approval Server stopped')

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming SSE client connections."""
        # Simple SSE implementation
        # In production, use a proper SSE library like sse-starlette or aiohttp-sse
        queue = asyncio.Queue()
        self._clients.add(queue)

        try:
            # Send initial connection message
            await self._send_sse_event(
                writer, 'connected', {'message': 'Connected to JIT Approval Server'}
            )

            # Keep connection alive and send events
            while True:
                event = await queue.get()
                await self._send_sse_event(writer, event['type'], event['data'])
        except asyncio.CancelledError:
            logger.info('SSE client disconnected')
        finally:
            self._clients.discard(queue)

    async def _send_sse_event(
        self, writer: asyncio.StreamWriter, event_type: str, data: dict
    ) -> None:
        """Send an SSE event to the client."""
        message = f'event: {event_type}\n'
        message += f'data: {json.dumps(data)}\n\n'
        writer.write(message.encode('utf-8'))
        await writer.drain()

    def request_approval(
        self, agent_name: str, tool_name: str, reason: str
    ) -> ApprovalRequestRecord:
        """Request JIT approval for a tool.

        Args:
            agent_name: Name of the agent requesting access.
            tool_name: Name of the tool.
            reason: Reason for the request.

        Returns:
            ApprovalRequestRecord with request details.
        """
        request_id = f'{agent_name}-{tool_name}-{int(time.time())}'

        # Create permission request
        request = PermissionRequest(
            tool_name=tool_name,
            agent_name=agent_name,
            reason=reason,
        )

        # Create record
        record = ApprovalRequestRecord(
            request_id=request_id,
            request=request,
            status=ApprovalStatus.PENDING,
            created_at=time.time(),
            timeout_seconds=self._timeout_seconds,
        )

        self._requests[request_id] = record

        # Broadcast to all connected clients (if server is running)
        if self._clients:
            asyncio.create_task(self._broadcast_request(record))

        # Wait for approval or timeout
        result = self._wait_for_approval(record)

        return result

    async def _broadcast_request(self, record: ApprovalRequestRecord) -> None:
        """Broadcast a request to all connected clients.

        Args:
            record: ApprovalRequestRecord to broadcast.
        """
        event_data = {
            'request_id': record.request_id,
            'agent_name': record.request.agent_name,
            'tool_name': record.request.tool_name,
            'reason': record.request.reason,
            'timeout_seconds': record.timeout_seconds,
            'created_at': record.created_at,
        }

        event = {'type': 'approval_request', 'data': event_data}

        for queue in self._clients:
            await queue.put(event)

    def _wait_for_approval(self, record: ApprovalRequestRecord) -> ApprovalRequestRecord:
        """Wait for approval or timeout.

        Args:
            record: ApprovalRequestRecord to wait for.

        Returns:
            Updated ApprovalRequestRecord with final status.
        """
        # In a real implementation, this would use async/await with timeout
        # For now, we'll simulate with a timeout check
        deadline = record.created_at + record.timeout_seconds

        while time.time() < deadline:
            if record.status != ApprovalStatus.PENDING:
                break
            time.sleep(1)

        # Check for timeout
        if record.status == ApprovalStatus.PENDING:
            record.status = ApprovalStatus.TIMEOUT
            logger.warning(
                f'Approval request {record.request_id} timed out after {self._timeout_seconds}s'
            )

        return record

    def approve_request(self, request_id: str) -> None:
        """Approve a pending approval request.

        Args:
            request_id: ID of the request to approve.
        """
        record = self._requests.get(request_id)
        if not record:
            logger.warning(f'Approval request not found: {request_id}')
            return

        if record.status != ApprovalStatus.PENDING:
            logger.warning(f'Request {request_id} already processed: {record.status.value}')
            return

        record.status = ApprovalStatus.APPROVED
        record.approved_at = time.time()
        record.request.approved = True

        # Update permission manager
        self._permission_manager.request_tool_approval(
            record.request.agent_name,
            record.request.tool_name,
            record.request.reason,
        )

        # Broadcast approval
        asyncio.create_task(self._broadcast_approval(record))

        logger.info(f'Approved request {request_id}')

    def reject_request(self, request_id: str) -> None:
        """Reject a pending approval request.

        Args:
            request_id: ID of the request to reject.
        """
        record = self._requests.get(request_id)
        if not record:
            logger.warning(f'Approval request not found: {request_id}')
            return

        if record.status != ApprovalStatus.PENDING:
            logger.warning(f'Request {request_id} already processed: {record.status.value}')
            return

        record.status = ApprovalStatus.REJECTED
        record.rejected_at = time.time()
        record.request.approved = False

        # Broadcast rejection
        asyncio.create_task(self._broadcast_rejection(record))

        logger.info(f'Rejected request {request_id}')

    async def _broadcast_approval(self, record: ApprovalRequestRecord) -> None:
        """Broadcast approval to all connected clients.

        Args:
            record: ApprovalRequestRecord to broadcast.
        """
        event_data = {
            'request_id': record.request_id,
            'status': record.status.value,
            'approved_at': record.approved_at,
        }

        event = {'type': 'approval_result', 'data': event_data}

        for queue in self._clients:
            await queue.put(event)

    async def _broadcast_rejection(self, record: ApprovalRequestRecord) -> None:
        """Broadcast rejection to all connected clients.

        Args:
            record: ApprovalRequestRecord to broadcast.
        """
        event_data = {
            'request_id': record.request_id,
            'status': record.status.value,
            'rejected_at': record.rejected_at,
        }

        event = {'type': 'approval_result', 'data': event_data}

        for queue in self._clients:
            await queue.put(event)

    def get_pending_requests(self) -> list[ApprovalRequestRecord]:
        """Get all pending approval requests.

        Returns:
            List of pending ApprovalRequestRecord instances.
        """
        return [
            record
            for record in self._requests.values()
            if record.status == ApprovalStatus.PENDING
        ]

    def get_request_status(self, request_id: str) -> Optional[ApprovalRequestRecord]:
        """Get the status of an approval request.

        Args:
            request_id: ID of the request.

        Returns:
            ApprovalRequestRecord if found, None otherwise.
        """
        return self._requests.get(request_id)

    def cleanup_old_requests(self) -> None:
        """Clean up old approval requests."""
        cutoff_time = time.time() - 3600  # 1 hour

        old_request_ids = [
            request_id
            for request_id, record in self._requests.items()
            if record.created_at < cutoff_time
        ]

        for request_id in old_request_ids:
            del self._requests[request_id]

        if old_request_ids:
            logger.info(f'Cleaned up {len(old_request_ids)} old approval requests')
