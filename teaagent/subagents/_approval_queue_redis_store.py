"""Redis-backed approval queue state for cross-process parent/subagent coordination."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

try:
    import redis
except ImportError:
    redis = None

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import request_from_dict

logger = logging.getLogger(__name__)


@dataclass
class RedisApprovalQueueConfig:
    """Configuration for Redis approval queue."""

    host: str = 'localhost'
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    key_prefix: str = 'approval_queue'
    connection_pool_size: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5


class RedisApprovalQueueStore:
    """Redis-backed approval queue state for cross-process coordination."""

    def __init__(
        self,
        config: Optional[RedisApprovalQueueConfig] = None,
        redis_client: Optional[redis.Redis] = None,
    ) -> None:
        if redis is None:
            raise ImportError(
                'Redis library not installed. Install with: pip install redis'
            )

        self.config = config or RedisApprovalQueueConfig()
        self._redis_client = redis_client

        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                ssl=self.config.ssl,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                decode_responses=True,
            )

        self._key_prefix = self.config.key_prefix

    @property
    def redis_client(self) -> redis.Redis:
        """Get the Redis client."""
        if self._redis_client is None:
            raise RuntimeError('Redis client not initialized')
        return self._redis_client

    def _request_key(self, parent_run_id: str, request_id: str) -> str:
        """Generate Redis key for a request."""
        safe_id = parent_run_id.replace('/', '_')
        return f'{self._key_prefix}:{safe_id}:request:{request_id}'

    def _batch_key(self, parent_run_id: str, batch_id: str) -> str:
        """Generate Redis key for a batch."""
        safe_id = parent_run_id.replace('/', '_')
        return f'{self._key_prefix}:{safe_id}:batch:{batch_id}'

    def _pending_set_key(self, parent_run_id: str) -> str:
        """Generate Redis key for pending request set."""
        safe_id = parent_run_id.replace('/', '_')
        return f'{self._key_prefix}:{safe_id}:pending'

    def _all_requests_key(self, parent_run_id: str) -> str:
        """Generate Redis key for all requests set."""
        safe_id = parent_run_id.replace('/', '_')
        return f'{self._key_prefix}:{safe_id}:all_requests'

    def _batches_set_key(self, parent_run_id: str) -> str:
        """Generate Redis key for batches set."""
        safe_id = parent_run_id.replace('/', '_')
        return f'{self._key_prefix}:{safe_id}:batches'

    def ping(self) -> bool:
        """Check Redis connection."""
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f'Redis ping failed: {e}')
            return False

    def save_request(
        self,
        parent_run_id: str,
        request: SubagentApprovalRequest,
    ) -> None:
        """Save a request to Redis."""
        key = self._request_key(parent_run_id, request.request_id)
        data = request.to_dict()
        self.redis_client.hset(key, mapping=data)

        # Add to pending set if pending
        if request.status == ApprovalRequestStatus.PENDING:
            pending_key = self._pending_set_key(parent_run_id)
            self.redis_client.sadd(pending_key, request.request_id)

        # Add to all requests set
        all_key = self._all_requests_key(parent_run_id)
        self.redis_client.sadd(all_key, request.request_id)

    def get_request(
        self,
        parent_run_id: str,
        request_id: str,
    ) -> Optional[SubagentApprovalRequest]:
        """Get a request from Redis."""
        key = self._request_key(parent_run_id, request_id)
        data = self.redis_client.hgetall(key)
        if not data:
            return None
        return request_from_dict(data)

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        """Update request status in Redis."""
        key = self._request_key(parent_run_id, request_id)
        data = self.redis_client.hgetall(key)
        if not data:
            return False

        if data.get('status') != ApprovalRequestStatus.PENDING.value:
            return False

        now = datetime.now(timezone.utc).isoformat()
        updates = {'status': status.value}

        if status == ApprovalRequestStatus.APPROVED:
            updates['approved_at'] = now
            updates['approved_by'] = approved_by
        elif status == ApprovalRequestStatus.DENIED:
            updates['denied_at'] = now
            updates['denial_reason'] = reason or 'Denied by human'

        self.redis_client.hset(key, mapping=updates)

        # Remove from pending set if no longer pending
        if status != ApprovalRequestStatus.PENDING:
            pending_key = self._pending_set_key(parent_run_id)
            self.redis_client.srem(pending_key, request_id)

        return True

    def get_pending_requests(
        self,
        parent_run_id: str,
    ) -> list[SubagentApprovalRequest]:
        """Get all pending requests from Redis."""
        pending_key = self._pending_set_key(parent_run_id)
        request_ids = self.redis_client.smembers(pending_key)

        pending: list[SubagentApprovalRequest] = []
        for request_id in request_ids:
            request = self.get_request(parent_run_id, request_id)
            if request and request.status == ApprovalRequestStatus.PENDING:
                pending.append(request)

        return pending

    def save_batch(
        self,
        parent_run_id: str,
        batch: ApprovalBatch,
    ) -> None:
        """Save a batch to Redis."""
        key = self._batch_key(parent_run_id, batch.batch_id)
        data = batch.to_dict()
        self.redis_client.hset(key, mapping=data)

        # Add to batches set
        batches_key = self._batches_set_key(parent_run_id)
        self.redis_client.sadd(batches_key, batch.batch_id)

    def get_batch(
        self,
        parent_run_id: str,
        batch_id: str,
    ) -> Optional[ApprovalBatch]:
        """Get a batch from Redis."""
        key = self._batch_key(parent_run_id, batch_id)
        data = self.redis_client.hgetall(key)
        if not data:
            return None
        # ApprovalBatch doesn't have from_dict, reconstruct manually
        batch = ApprovalBatch(
            batch_id=data.get('batch_id', batch_id),
            parent_run_id=data.get('parent_run_id', parent_run_id),
            created_at=data.get('created_at', ''),
            status=ApprovalRequestStatus(data.get('status', 'pending')),
        )
        return batch

    def get_all_request_ids(
        self,
        parent_run_id: str,
    ) -> set[str]:
        """Get all request IDs for a parent run."""
        all_key = self._all_requests_key(parent_run_id)
        return set(self.redis_client.smembers(all_key))

    def get_all_batch_ids(
        self,
        parent_run_id: str,
    ) -> set[str]:
        """Get all batch IDs for a parent run."""
        batches_key = self._batches_set_key(parent_run_id)
        return set(self.redis_client.smembers(batches_key))

    def delete_request(
        self,
        parent_run_id: str,
        request_id: str,
    ) -> bool:
        """Delete a request from Redis."""
        key = self._request_key(parent_run_id, request_id)
        result = self.redis_client.delete(key)

        # Remove from sets
        pending_key = self._pending_set_key(parent_run_id)
        self.redis_client.srem(pending_key, request_id)

        all_key = self._all_requests_key(parent_run_id)
        self.redis_client.srem(all_key, request_id)

        return result > 0

    def delete_batch(
        self,
        parent_run_id: str,
        batch_id: str,
    ) -> bool:
        """Delete a batch from Redis."""
        key = self._batch_key(parent_run_id, batch_id)
        result = self.redis_client.delete(key)

        # Remove from batches set
        batches_key = self._batches_set_key(parent_run_id)
        self.redis_client.srem(batches_key, batch_id)

        return result > 0

    def delete_parent_run(self, parent_run_id: str) -> int:
        """Delete all data for a parent run."""
        deleted = 0

        # Delete all requests
        request_ids = self.get_all_request_ids(parent_run_id)
        for request_id in request_ids:
            if self.delete_request(parent_run_id, request_id):
                deleted += 1

        # Delete all batches
        batch_ids = self.get_all_batch_ids(parent_run_id)
        for batch_id in batch_ids:
            if self.delete_batch(parent_run_id, batch_id):
                deleted += 1

        # Delete sets
        keys_to_delete = [
            self._pending_set_key(parent_run_id),
            self._all_requests_key(parent_run_id),
            self._batches_set_key(parent_run_id),
        ]
        deleted += self.redis_client.delete(*keys_to_delete)

        return deleted

    def list_parent_run_ids(self) -> list[str]:
        """List all parent run IDs in Redis."""
        pattern = f'{self._key_prefix}:*:all_requests'
        keys = self.redis_client.keys(pattern)

        parent_run_ids = []
        for key in keys:
            # Extract parent_run_id from key pattern
            # Format: approval_queue:{parent_run_id}:all_requests
            parts = key.split(':')
            if len(parts) >= 3:
                parent_run_id = parts[1].replace('_', '/')
                parent_run_ids.append(parent_run_id)

        return parent_run_ids

    def exists(self, parent_run_id: str) -> bool:
        """Check if a parent run has any data in Redis."""
        all_key = self._all_requests_key(parent_run_id)
        return self.redis_client.exists(all_key) > 0
