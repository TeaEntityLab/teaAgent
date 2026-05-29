"""Centralized Approval Queue for Subagent Destructive Tool Requests.

This module implements a centralized approval queue that aggregates destructive
tool requests from multiple subagents running in parallel/tournament mode.
The parent TUI can review and approve/deny requests batched by subagent lineage.

Key design decisions:
- Subagent destructive requests are queued, not immediately prompted
- Parent TUI shows aggregated requests with full lineage context
- Human can approve/deny individually or in batch
- Denied requests trigger fallback strategies in respective subagents
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApprovalRequestStatus(Enum):
    """Status of a subagent approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SubagentApprovalRequest:
    """A destructive tool request from a subagent requiring approval."""
    request_id: str
    subagent_id: str
    parent_run_id: str
    subagent_name: str
    tool_name: str
    tool_arguments: dict[str, Any]
    permission_mode: str
    isolation: str
    batch_index: Optional[int] = None
    worktree_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING
    approved_at: Optional[str] = None
    denied_at: Optional[str] = None
    denial_reason: Optional[str] = None
    timeout_seconds: int = 180  # 3 minutes default

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "request_id": self.request_id,
            "subagent_id": self.subagent_id,
            "parent_run_id": self.parent_run_id,
            "subagent_name": self.subagent_name,
            "tool_name": self.tool_name,
            "tool_arguments": self.tool_arguments,
            "permission_mode": self.permission_mode,
            "isolation": self.isolation,
            "batch_index": self.batch_index,
            "worktree_path": self.worktree_path,
            "created_at": self.created_at,
            "status": self.status.value,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.approved_at:
            payload["approved_at"] = self.approved_at
        if self.denied_at:
            payload["denied_at"] = self.denied_at
        if self.denial_reason:
            payload["denial_reason"] = self.denial_reason
        return payload


@dataclass
class ApprovalBatch:
    """A batch of approval requests grouped for parent TUI review."""
    batch_id: str
    parent_run_id: str
    requests: list[SubagentApprovalRequest] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING

    def add_request(self, request: SubagentApprovalRequest) -> None:
        self.requests.append(request)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "parent_run_id": self.parent_run_id,
            "requests": [r.to_dict() for r in self.requests],
            "created_at": self.created_at,
            "status": self.status.value,
            "request_count": len(self.requests),
        }


class CentralizedApprovalQueue:
    """Centralized queue for subagent destructive tool approval requests.

    This queue aggregates destructive tool requests from multiple subagents
    and provides a unified interface for the parent TUI to review and approve/deny.
    """

    def __init__(self, parent_run_id: str) -> None:
        self._parent_run_id = parent_run_id
        self._requests: dict[str, SubagentApprovalRequest] = {}
        self._batches: dict[str, ApprovalBatch] = {}
        self._pending_futures: dict[str, asyncio.Future[bool]] = {}
        self._lock = asyncio.Lock()

    def generate_request_id(self) -> str:
        return uuid4().hex

    def generate_batch_id(self) -> str:
        return uuid4().hex

    async def submit_request(
        self,
        subagent_id: str,
        subagent_name: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        permission_mode: str,
        isolation: str,
        batch_index: Optional[int] = None,
        worktree_path: Optional[str] = None,
    ) -> bool:
        """Submit a destructive tool request for approval.

        Returns True if approved, False if denied or timed out.
        """
        request_id = self.generate_request_id()
        request = SubagentApprovalRequest(
            request_id=request_id,
            subagent_id=subagent_id,
            parent_run_id=self._parent_run_id,
            subagent_name=subagent_name,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            permission_mode=permission_mode,
            isolation=isolation,
            batch_index=batch_index,
            worktree_path=worktree_path,
        )

        async with self._lock:
            self._requests[request_id] = request
            # Create a future for this request
            future: asyncio.Future[bool] = asyncio.Future()
            self._pending_futures[request_id] = future

        logger.info(
            f"Submitted approval request {request_id} from subagent {subagent_name} "
            f"for tool {tool_name}"
        )

        try:
            # Wait for approval/deny with timeout
            result = await asyncio.wait_for(
                future, timeout=request.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                if request_id in self._requests:
                    self._requests[request_id].status = ApprovalRequestStatus.TIMEOUT
            logger.warning(f"Approval request {request_id} timed out")
            return False
        finally:
            async with self._lock:
                self._pending_futures.pop(request_id, None)

    async def approve_request(
        self, request_id: str, approved_by: str = "human"
    ) -> bool:
        """Approve a specific request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                logger.warning(f"Request {request_id} not found")
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(
                    f"Request {request_id} already has status {request.status.value}"
                )
                return False

            request.status = ApprovalRequestStatus.APPROVED
            request.approved_at = datetime.now(timezone.utc).isoformat()

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.set_result(True)

        logger.info(f"Approved request {request_id} by {approved_by}")
        return True

    async def deny_request(
        self, request_id: str, reason: str = "Denied by human"
    ) -> bool:
        """Deny a specific request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                logger.warning(f"Request {request_id} not found")
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(
                    f"Request {request_id} already has status {request.status.value}"
                )
                return False

            request.status = ApprovalRequestStatus.DENIED
            request.denied_at = datetime.now(timezone.utc).isoformat()
            request.denial_reason = reason

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.set_result(False)

        logger.info(f"Denied request {request_id}: {reason}")
        return True

    async def approve_batch(self, batch_id: str, approved_by: str = "human") -> int:
        """Approve all requests in a batch. Returns count of approved requests."""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                logger.warning(f"Batch {batch_id} not found")
                return 0

            approved_count = 0
            for request in batch.requests:
                if request.status == ApprovalRequestStatus.PENDING:
                    request.status = ApprovalRequestStatus.APPROVED
                    request.approved_at = datetime.now(timezone.utc).isoformat()

                    future = self._pending_futures.get(request.request_id)
                    if future and not future.done():
                        future.set_result(True)
                    approved_count += 1

            batch.status = ApprovalRequestStatus.APPROVED

        logger.info(f"Approved {approved_count} requests in batch {batch_id}")
        return approved_count

    async def deny_batch(
        self, batch_id: str, reason: str = "Batch denied by human"
    ) -> int:
        """Deny all requests in a batch. Returns count of denied requests."""
        async with self._lock:
            batch = self._batches.get(batch_id)
            if not batch:
                logger.warning(f"Batch {batch_id} not found")
                return 0

            denied_count = 0
            for request in batch.requests:
                if request.status == ApprovalRequestStatus.PENDING:
                    request.status = ApprovalRequestStatus.DENIED
                    request.denied_at = datetime.now(timezone.utc).isoformat()
                    request.denial_reason = reason

                    future = self._pending_futures.get(request.request_id)
                    if future and not future.done():
                        future.set_result(False)
                    denied_count += 1

            batch.status = ApprovalRequestStatus.DENIED

        logger.info(f"Denied {denied_count} requests in batch {batch_id}: {reason}")
        return denied_count

    def create_batch(self, request_ids: list[str]) -> str:
        """Create a batch from existing requests for group review."""
        batch_id = self.generate_batch_id()
        batch = ApprovalBatch(batch_id=batch_id, parent_run_id=self._parent_run_id)

        for request_id in request_ids:
            request = self._requests.get(request_id)
            if request and request.status == ApprovalRequestStatus.PENDING:
                batch.add_request(request)

        self._batches[batch_id] = batch
        logger.info(f"Created batch {batch_id} with {len(batch.requests)} requests")
        return batch_id

    def get_pending_requests(self) -> list[SubagentApprovalRequest]:
        """Get all pending requests."""
        return [
            r for r in self._requests.values() if r.status == ApprovalRequestStatus.PENDING
        ]

    def get_request(self, request_id: str) -> Optional[SubagentApprovalRequest]:
        """Get a specific request by ID."""
        return self._requests.get(request_id)

    def get_batch(self, batch_id: str) -> Optional[ApprovalBatch]:
        """Get a specific batch by ID."""
        return self._batches.get(batch_id)

    def get_all_batches(self) -> list[ApprovalBatch]:
        """Get all batches."""
        return list(self._batches.values())

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending request (e.g., if subagent is terminated)."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                return False

            request.status = ApprovalRequestStatus.CANCELLED

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.cancel()

        logger.info(f"Cancelled request {request_id}")
        return True

    async def cleanup(self) -> None:
        """Clean up completed requests to prevent memory leaks."""
        async with self._lock:
            to_remove = [
                rid
                for rid, req in self._requests.items()
                if req.status
                in {
                    ApprovalRequestStatus.APPROVED,
                    ApprovalRequestStatus.DENIED,
                    ApprovalRequestStatus.TIMEOUT,
                    ApprovalRequestStatus.CANCELLED,
                }
                and rid not in self._pending_futures
            ]
            for rid in to_remove:
                self._requests.pop(rid, None)

            # Clean up empty batches
            empty_batches = [
                bid for bid, batch in self._batches.items() if not batch.requests
            ]
            for bid in empty_batches:
                self._batches.pop(bid, None)

        if to_remove or empty_batches:
            logger.info(f"Cleaned up {len(to_remove)} requests, {len(empty_batches)} batches")


# Global registry for parent run_id to queue instances
_approval_queues: dict[str, CentralizedApprovalQueue] = {}
_queue_lock = asyncio.Lock()


def get_approval_queue(parent_run_id: str) -> CentralizedApprovalQueue:
    """Get or create the approval queue for a given parent run."""
    # This is a synchronous wrapper for the async version
    # In practice, this should be called from an async context
    if parent_run_id not in _approval_queues:
        _approval_queues[parent_run_id] = CentralizedApprovalQueue(parent_run_id)
    return _approval_queues[parent_run_id]


async def get_approval_queue_async(parent_run_id: str) -> CentralizedApprovalQueue:
    """Get or create the approval queue for a given parent run (async)."""
    async with _queue_lock:
        if parent_run_id not in _approval_queues:
            _approval_queues[parent_run_id] = CentralizedApprovalQueue(
                parent_run_id
            )
        return _approval_queues[parent_run_id]


async def cleanup_queue(parent_run_id: str) -> None:
    """Clean up the approval queue for a completed parent run."""
    async with _queue_lock:
        queue = _approval_queues.pop(parent_run_id, None)
        if queue:
            await queue.cleanup()
