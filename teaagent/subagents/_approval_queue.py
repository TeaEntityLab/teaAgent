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
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.runner._types import ApprovalHandler, ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalRequestStatus(Enum):
    """Status of a subagent approval request."""

    PENDING = 'pending'
    APPROVED = 'approved'
    DENIED = 'denied'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'


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
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING
    approved_at: Optional[str] = None
    denied_at: Optional[str] = None
    denial_reason: Optional[str] = None
    timeout_seconds: int = 180  # 3 minutes default

    def to_dict(self) -> dict[str, Any]:
        payload = {
            'request_id': self.request_id,
            'subagent_id': self.subagent_id,
            'parent_run_id': self.parent_run_id,
            'subagent_name': self.subagent_name,
            'tool_name': self.tool_name,
            'tool_arguments': self.tool_arguments,
            'permission_mode': self.permission_mode,
            'isolation': self.isolation,
            'batch_index': self.batch_index,
            'worktree_path': self.worktree_path,
            'created_at': self.created_at,
            'status': self.status.value,
            'timeout_seconds': self.timeout_seconds,
        }
        if self.approved_at:
            payload['approved_at'] = self.approved_at
        if self.denied_at:
            payload['denied_at'] = self.denied_at
        if self.denial_reason:
            payload['denial_reason'] = self.denial_reason
        return payload


@dataclass
class ApprovalBatch:
    """A batch of approval requests grouped for parent TUI review."""

    batch_id: str
    parent_run_id: str
    requests: list[SubagentApprovalRequest] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING

    def add_request(self, request: SubagentApprovalRequest) -> None:
        self.requests.append(request)

    def to_dict(self) -> dict[str, Any]:
        return {
            'batch_id': self.batch_id,
            'parent_run_id': self.parent_run_id,
            'requests': [r.to_dict() for r in self.requests],
            'created_at': self.created_at,
            'status': self.status.value,
            'request_count': len(self.requests),
        }


class CentralizedApprovalQueue:
    """Centralized queue for subagent destructive tool approval requests.

    This queue aggregates destructive tool requests from multiple subagents
    and provides a unified interface for the parent TUI to review and approve/deny.
    """

    def __init__(
        self,
        parent_run_id: str,
        *,
        workspace_root: Optional[Path] = None,
    ) -> None:
        self._parent_run_id = parent_run_id
        self._workspace_root = (
            Path(workspace_root).resolve() if workspace_root else None
        )
        self._requests: dict[str, SubagentApprovalRequest] = {}
        self._batches: dict[str, ApprovalBatch] = {}
        self._pending_futures: dict[str, asyncio.Future[bool]] = {}
        self._sync_waiters: dict[str, threading.Event] = {}
        self._sync_results: dict[str, bool] = {}
        self._lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        self._store = None
        if self._workspace_root is not None:
            from teaagent.subagents._approval_queue_store import ApprovalQueueStore

            self._store = ApprovalQueueStore(self._workspace_root)
            self.reload_from_store()

    def reload_from_store(self) -> None:
        """Merge on-disk queue state (for cross-process approve/deny)."""
        if self._store is None:
            return
        from teaagent.subagents._approval_queue_store import request_from_dict

        snapshot = self._store.load(self._parent_run_id)
        with self._sync_lock:
            for request_id, raw in snapshot.requests.items():
                loaded = request_from_dict(raw)
                existing = self._requests.get(request_id)
                if existing is None:
                    self._requests[request_id] = loaded
                    continue
                if existing.status == ApprovalRequestStatus.PENDING:
                    existing.status = loaded.status
                    existing.approved_at = loaded.approved_at
                    existing.denied_at = loaded.denied_at
                    existing.denial_reason = loaded.denial_reason
                    if loaded.status == ApprovalRequestStatus.APPROVED:
                        self._sync_results[request_id] = True
                        event = self._sync_waiters.get(request_id)
                        if event is not None:
                            event.set()
                    elif loaded.status in {
                        ApprovalRequestStatus.DENIED,
                        ApprovalRequestStatus.CANCELLED,
                    }:
                        self._sync_results[request_id] = False
                        event = self._sync_waiters.get(request_id)
                        if event is not None:
                            event.set()

    def _persist(self) -> None:
        if self._store is not None:
            self._store.save(self._parent_run_id, self._requests, self._batches)

    def generate_request_id(self) -> str:
        return uuid4().hex

    def generate_batch_id(self) -> str:
        return uuid4().hex

    def submit_request_sync(
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
        """Submit a destructive tool request and block until approved/denied/timeout."""
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
        event = threading.Event()
        with self._sync_lock:
            self._requests[request_id] = request
            self._sync_waiters[request_id] = event

        self._persist()
        logger.info(
            'Submitted sync approval request %s from subagent %s for tool %s',
            request_id,
            subagent_name,
            tool_name,
        )

        deadline = time.monotonic() + request.timeout_seconds
        poll_interval = 0.25
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if self._store is not None:
                self.reload_from_store()
            if event.wait(timeout=min(poll_interval, max(remaining, 0))):
                break
            with self._sync_lock:
                current = self._requests.get(request_id)
                if current is None:
                    continue
                if current.status == ApprovalRequestStatus.APPROVED:
                    self._sync_results[request_id] = True
                    event.set()
                    break
                if current.status in {
                    ApprovalRequestStatus.DENIED,
                    ApprovalRequestStatus.CANCELLED,
                }:
                    self._sync_results[request_id] = False
                    event.set()
                    break
        else:
            with self._sync_lock:
                if request_id in self._requests:
                    self._requests[request_id].status = ApprovalRequestStatus.TIMEOUT
                self._sync_waiters.pop(request_id, None)
                self._sync_results.pop(request_id, None)
            self._persist()
            logger.warning('Sync approval request %s timed out', request_id)
            return False

        with self._sync_lock:
            result = self._sync_results.pop(request_id, False)
            self._sync_waiters.pop(request_id, None)
        return result

    def approve_request_sync(self, request_id: str, approved_by: str = 'human') -> bool:
        """Approve a pending sync request (parent TUI / CLI)."""
        with self._sync_lock:
            request = self._requests.get(request_id)
            if not request or request.status != ApprovalRequestStatus.PENDING:
                return False
            request.status = ApprovalRequestStatus.APPROVED
            request.approved_at = datetime.now(timezone.utc).isoformat()
            self._sync_results[request_id] = True
            event = self._sync_waiters.get(request_id)
        if event is not None:
            event.set()
        self._persist()
        logger.info('Approved sync request %s by %s', request_id, approved_by)
        return True

    def approve_all_pending_sync(self, approved_by: str = 'human') -> int:
        """Approve every pending sync request. Returns count approved."""
        approved = 0
        for request in list(self.get_pending_requests()):
            if self.approve_request_sync(request.request_id, approved_by=approved_by):
                approved += 1
        return approved

    def deny_all_pending_sync(
        self, reason: str = 'Denied by human', denied_by: str = 'human'
    ) -> int:
        """Deny every pending sync request. Returns count denied."""
        denied = 0
        for request in list(self.get_pending_requests()):
            if self.deny_request_sync(request.request_id, reason=reason):
                denied += 1
        return denied

    def deny_request_sync(
        self, request_id: str, reason: str = 'Denied by human'
    ) -> bool:
        """Deny a pending sync request (parent TUI / CLI)."""
        with self._sync_lock:
            request = self._requests.get(request_id)
            if not request or request.status != ApprovalRequestStatus.PENDING:
                return False
            request.status = ApprovalRequestStatus.DENIED
            request.denied_at = datetime.now(timezone.utc).isoformat()
            request.denial_reason = reason
            self._sync_results[request_id] = False
            event = self._sync_waiters.get(request_id)
        if event is not None:
            event.set()
        self._persist()
        logger.info('Denied sync request %s: %s', request_id, reason)
        return True

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
            with self._sync_lock:
                self._requests[request_id] = request
            # Create a future for this request
            future: asyncio.Future[bool] = asyncio.Future()
            self._pending_futures[request_id] = future

        logger.info(
            f'Submitted approval request {request_id} from subagent {subagent_name} '
            f'for tool {tool_name}'
        )

        try:
            # Wait for approval/deny with timeout
            result = await asyncio.wait_for(future, timeout=request.timeout_seconds)
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                with self._sync_lock:
                    if request_id in self._requests:
                        self._requests[request_id].status = ApprovalRequestStatus.TIMEOUT
            logger.warning(f'Approval request {request_id} timed out')
            return False
        finally:
            async with self._lock:
                self._pending_futures.pop(request_id, None)

    async def approve_request(
        self, request_id: str, approved_by: str = 'human'
    ) -> bool:
        """Approve a specific request."""
        async with self._lock:
            with self._sync_lock:
                request = self._requests.get(request_id)
                if not request:
                    logger.warning(f'Request {request_id} not found')
                    return False

                if request.status != ApprovalRequestStatus.PENDING:
                    logger.warning(
                        f'Request {request_id} already has status {request.status.value}'
                    )
                    return False

                request.status = ApprovalRequestStatus.APPROVED
                request.approved_at = datetime.now(timezone.utc).isoformat()

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.set_result(True)

        logger.info(f'Approved request {request_id} by {approved_by}')
        return True

    async def deny_request(
        self, request_id: str, reason: str = 'Denied by human'
    ) -> bool:
        """Deny a specific request."""
        async with self._lock:
            with self._sync_lock:
                request = self._requests.get(request_id)
                if not request:
                    logger.warning(f'Request {request_id} not found')
                    return False

                if request.status != ApprovalRequestStatus.PENDING:
                    logger.warning(
                        f'Request {request_id} already has status {request.status.value}'
                    )
                    return False

                request.status = ApprovalRequestStatus.DENIED
                request.denied_at = datetime.now(timezone.utc).isoformat()
                request.denial_reason = reason

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.set_result(False)

        logger.info(f'Denied request {request_id}: {reason}')
        return True

    async def approve_batch(self, batch_id: str, approved_by: str = 'human') -> int:
        """Approve all requests in a batch. Returns count of approved requests."""
        async with self._lock:
            with self._sync_lock:
                batch = self._batches.get(batch_id)
                if not batch:
                    logger.warning(f'Batch {batch_id} not found')
                    return 0

                approved_count = 0
                for request in batch.requests:
                    if request.status == ApprovalRequestStatus.PENDING:
                        request.status = ApprovalRequestStatus.APPROVED
                        request.approved_at = datetime.now(timezone.utc).isoformat()
                        approved_count += 1

                batch.status = ApprovalRequestStatus.APPROVED

            for request in batch.requests:
                if request.status == ApprovalRequestStatus.APPROVED:
                    future = self._pending_futures.get(request.request_id)
                    if future and not future.done():
                        future.set_result(True)

        logger.info(f'Approved {approved_count} requests in batch {batch_id}')
        return approved_count

    async def deny_batch(
        self, batch_id: str, reason: str = 'Batch denied by human'
    ) -> int:
        """Deny all requests in a batch. Returns count of denied requests."""
        async with self._lock:
            with self._sync_lock:
                batch = self._batches.get(batch_id)
                if not batch:
                    logger.warning(f'Batch {batch_id} not found')
                    return 0

                denied_count = 0
                for request in batch.requests:
                    if request.status == ApprovalRequestStatus.PENDING:
                        request.status = ApprovalRequestStatus.DENIED
                        request.denied_at = datetime.now(timezone.utc).isoformat()
                        request.denial_reason = reason
                        denied_count += 1

                batch.status = ApprovalRequestStatus.DENIED

            for request in batch.requests:
                if request.status == ApprovalRequestStatus.DENIED:
                    future = self._pending_futures.get(request.request_id)
                    if future and not future.done():
                        future.set_result(False)

        logger.info(f'Denied {denied_count} requests in batch {batch_id}: {reason}')
        return denied_count

    def create_batch(self, request_ids: list[str]) -> str:
        """Create a batch from existing requests for group review."""
        batch_id = self.generate_batch_id()
        batch = ApprovalBatch(batch_id=batch_id, parent_run_id=self._parent_run_id)

        with self._sync_lock:
            for request_id in request_ids:
                request = self._requests.get(request_id)
                if request and request.status == ApprovalRequestStatus.PENDING:
                    batch.add_request(request)

            self._batches[batch_id] = batch
        logger.info(f'Created batch {batch_id} with {len(batch.requests)} requests')
        return batch_id

    def get_pending_requests(self) -> list[SubagentApprovalRequest]:
        """Get all pending requests."""
        with self._sync_lock:
            return [
                r
                for r in self._requests.values()
                if r.status == ApprovalRequestStatus.PENDING
            ]

    def get_request(self, request_id: str) -> Optional[SubagentApprovalRequest]:
        """Get a specific request by ID."""
        with self._sync_lock:
            return self._requests.get(request_id)

    def get_batch(self, batch_id: str) -> Optional[ApprovalBatch]:
        """Get a specific batch by ID."""
        with self._sync_lock:
            return self._batches.get(batch_id)

    def get_all_batches(self) -> list[ApprovalBatch]:
        """Get all batches."""
        with self._sync_lock:
            return list(self._batches.values())

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending request (e.g., if subagent is terminated)."""
        async with self._lock:
            with self._sync_lock:
                request = self._requests.get(request_id)
                if not request:
                    return False

                if request.status != ApprovalRequestStatus.PENDING:
                    return False

                request.status = ApprovalRequestStatus.CANCELLED

            future = self._pending_futures.get(request_id)
            if future and not future.done():
                future.cancel()

        logger.info(f'Cancelled request {request_id}')
        return True

    async def cleanup(self) -> None:
        """Clean up completed requests to prevent memory leaks."""
        async with self._lock:
            with self._sync_lock:
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
            logger.info(
                f'Cleaned up {len(to_remove)} requests, {len(empty_batches)} batches'
            )


# Global registry for (workspace, parent_run_id) -> queue instances
_approval_queues: dict[tuple[str, str], CentralizedApprovalQueue] = {}
_queue_lock = threading.Lock()


def _queue_key(workspace_root: Optional[Path], parent_run_id: str) -> tuple[str, str]:
    if workspace_root is None:
        return ('', parent_run_id)
    return (str(Path(workspace_root).resolve()), parent_run_id)


def list_active_parent_run_ids(
    workspace_root: Optional[Path] = None,
) -> list[str]:
    """Return parent run IDs with in-memory or on-disk approval queues."""
    root_key = (
        str(Path(workspace_root).resolve()) if workspace_root is not None else None
    )
    keys: set[str] = set()
    for ws, parent_id in _approval_queues:
        if root_key is None or ws == root_key:
            keys.add(parent_id)
    if workspace_root is not None:
        from teaagent.subagents._approval_queue_store import ApprovalQueueStore

        keys.update(ApprovalQueueStore(workspace_root).list_parent_run_ids())
    return sorted(keys)


def snapshot_pending_subagent_requests(
    parent_run_id: Optional[str] = None,
    *,
    workspace_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Serialize pending subagent approval requests for CLI/TUI."""
    items: list[dict[str, Any]] = []
    parent_ids = (
        [parent_run_id] if parent_run_id else list_active_parent_run_ids(workspace_root)
    )
    for pid in parent_ids:
        queue = get_approval_queue(pid, workspace_root=workspace_root)
        queue.reload_from_store()
        for request in queue.get_pending_requests():
            payload = request.to_dict()
            payload['parent_run_id'] = pid
            items.append(payload)
    return items


def try_get_approval_queue(
    parent_run_id: str,
    *,
    workspace_root: Optional[Path] = None,
) -> Optional[CentralizedApprovalQueue]:
    """Return an existing queue without creating an empty on-disk file."""
    key = _queue_key(workspace_root, parent_run_id)
    if key in _approval_queues:
        return _approval_queues[key]
    if workspace_root is not None:
        from teaagent.subagents._approval_queue_store import ApprovalQueueStore

        if ApprovalQueueStore(workspace_root).exists(parent_run_id):
            return get_approval_queue(parent_run_id, workspace_root=workspace_root)
    return None


def get_approval_queue(
    parent_run_id: str,
    *,
    workspace_root: Optional[Path] = None,
) -> CentralizedApprovalQueue:
    """Get or create the approval queue for a given parent run."""
    key = _queue_key(workspace_root, parent_run_id)
    with _queue_lock:
        if key not in _approval_queues:
            _approval_queues[key] = CentralizedApprovalQueue(
                parent_run_id, workspace_root=workspace_root
            )
        return _approval_queues[key]


def approve_request_cross_process(
    workspace_root: Path,
    parent_run_id: str,
    request_id: str,
    *,
    approved_by: str = 'human',
) -> bool:
    """Approve via disk when the parent process holds the in-memory waiter."""
    from teaagent.subagents._approval_queue_store import ApprovalQueueStore

    store = ApprovalQueueStore(workspace_root)
    ok = store.update_request_status(
        parent_run_id,
        request_id,
        ApprovalRequestStatus.APPROVED,
        approved_by=approved_by,
    )
    if ok:
        queue = try_get_approval_queue(parent_run_id, workspace_root=workspace_root)
        if queue is not None:
            queue.reload_from_store()
    return ok


def deny_request_cross_process(
    workspace_root: Path,
    parent_run_id: str,
    request_id: str,
    *,
    reason: str = 'Denied by human',
) -> bool:
    from teaagent.subagents._approval_queue_store import ApprovalQueueStore

    store = ApprovalQueueStore(workspace_root)
    ok = store.update_request_status(
        parent_run_id,
        request_id,
        ApprovalRequestStatus.DENIED,
        reason=reason,
    )
    if ok:
        queue = try_get_approval_queue(parent_run_id, workspace_root=workspace_root)
        if queue is not None:
            queue.reload_from_store()
    return ok


async def get_approval_queue_async(
    parent_run_id: str,
    *,
    workspace_root: Optional[Path] = None,
) -> CentralizedApprovalQueue:
    """Get or create the approval queue for a given parent run (async)."""
    return get_approval_queue(parent_run_id, workspace_root=workspace_root)


def make_centralized_subagent_approval_handler(
    *,
    parent_run_id: str,
    subagent_id: str,
    subagent_name: str,
    permission_mode: str,
    isolation: str,
    batch_index: Optional[int] = None,
    worktree_path: Optional[str] = None,
    workspace_root: Optional[Path] = None,
) -> ApprovalHandler:
    """Route destructive subagent tool prompts through the parent approval queue."""

    queue = get_approval_queue(parent_run_id, workspace_root=workspace_root)

    def handler(request: ApprovalRequest) -> bool:
        return queue.submit_request_sync(
            subagent_id=subagent_id,
            subagent_name=subagent_name,
            tool_name=request.tool_name,
            tool_arguments=request.arguments,
            permission_mode=permission_mode,
            isolation=isolation,
            batch_index=batch_index,
            worktree_path=worktree_path,
        )

    return handler


def should_use_centralized_approval(
    *,
    parent_run_id: str,
    batch_index: Optional[int],
    parallel_mode: bool = False,
) -> bool:
    """True when subagent destructive approvals belong in the parent queue."""
    if not parent_run_id.strip():
        return False
    return batch_index is not None or parallel_mode


async def cleanup_queue(
    parent_run_id: str,
    *,
    workspace_root: Optional[Path] = None,
) -> None:
    """Clean up the approval queue for a completed parent run."""
    key = _queue_key(workspace_root, parent_run_id)
    with _queue_lock:
        queue = _approval_queues.pop(key, None)
    if queue:
        await queue.cleanup()
