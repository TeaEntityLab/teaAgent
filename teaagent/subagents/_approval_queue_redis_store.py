"""Redis-backed approval queue state for cross-process parent/subagent coordination."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

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


class SecurityError(Exception):
    """Security-related error for Redis connections."""

    pass


@dataclass
class RedisApprovalQueueConfig:
    """Configuration for Redis approval queue."""

    host: str = 'localhost'
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    ssl_certfile: Optional[str] = None  # Path to client certificate
    ssl_keyfile: Optional[str] = None  # Path to client private key
    ssl_ca_certs: Optional[str] = None  # Path to CA certificates
    ssl_cert_reqs: str = 'required'  # SSL certificate requirements
    key_prefix: str = 'approval_queue'
    connection_pool_size: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    username: Optional[str] = None  # Redis 6.0+ ACL username
    enable_acl: bool = False  # Enable ACL-based authentication
    allowed_networks: Optional[list[str]] = None  # Allowed network CIDR blocks
    enable_pipelining: bool = True  # Enable Redis pipelining for batch operations
    enable_local_cache: bool = True  # Enable local caching for read operations
    cache_ttl_seconds: int = 5  # Cache TTL in seconds
    sentinel_hosts: Optional[list[str]] = None  # Redis Sentinel hosts for HA
    sentinel_master_name: Optional[str] = None  # Sentinel master name
    sentinel_socket_timeout: int = 5  # Sentinel socket timeout
    cluster_nodes: Optional[list[str]] = None  # Redis Cluster nodes
    cluster_max_connections: int = 10  # Max connections for cluster
    enable_slow_query_log: bool = True  # Enable slow query logging
    slow_query_threshold_ms: int = 100  # Slow query threshold in milliseconds
    enable_memory_management: bool = True  # Enable memory management
    max_memory_mb: Optional[int] = None  # Max memory in MB
    eviction_policy: str = 'allkeys-lru'  # Redis eviction policy
    operation_timeout_seconds: int = 30  # Operation timeout in seconds
    enable_retry: bool = True  # Enable retry logic for failed operations
    max_retries: int = 3  # Maximum number of retries
    retry_delay_ms: int = 100  # Delay between retries in milliseconds


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

        # Local cache for read operations
        self._cache: dict[str, tuple[SubagentApprovalRequest, float]] = {}

        # Slow query logging
        self._slow_queries: list[dict[str, Any]] = []

        # Connection pool monitoring
        self._connection_stats: dict[str, Any] = {
            'total_operations': 0,
            'failed_operations': 0,
            'slow_operations': 0,
        }

        # Validate network segmentation
        if self.config.allowed_networks:
            self._validate_network_access()

        if self._redis_client is None:
            # Check if using Redis Cluster
            if self.config.cluster_nodes:
                self._init_cluster_client()
            # Check if using Sentinel for HA
            elif self.config.sentinel_hosts and self.config.sentinel_master_name:
                self._init_sentinel_client()
            else:
                self._init_redis_client()

    def _init_redis_client(self) -> None:
        """Initialize regular Redis client."""
        # Build SSL configuration
        ssl_context = None
        if self.config.ssl:
            import ssl

            ssl_context = ssl.create_default_context(cafile=self.config.ssl_ca_certs)
            if self.config.ssl_certfile and self.config.ssl_keyfile:
                ssl_context.load_cert_chain(
                    certfile=self.config.ssl_certfile,
                    keyfile=self.config.ssl_keyfile,
                )
            ssl_context.verify_mode = getattr(
                ssl, f'CERT_{self.config.ssl_cert_reqs.upper()}', ssl.CERT_REQUIRED
            )

        # Build connection parameters
        connection_params = {
            'host': self.config.host,
            'port': self.config.port,
            'db': self.config.db,
            'socket_timeout': self.config.socket_timeout,
            'socket_connect_timeout': self.config.socket_connect_timeout,
            'decode_responses': True,
        }

        # Add SSL configuration
        if ssl_context:
            connection_params['ssl'] = ssl_context

        # Add authentication
        if self.config.enable_acl and self.config.username:
            connection_params['username'] = self.config.username
            connection_params['password'] = self.config.password
        elif self.config.password:
            connection_params['password'] = self.config.password

        self._redis_client = redis.Redis(**connection_params)

        self._key_prefix = self.config.key_prefix

        # Configure memory management
        self.configure_memory_management()

    def _init_cluster_client(self) -> None:
        """Initialize Redis Cluster client."""
        try:
            from redis.cluster import RedisCluster

            # Build SSL configuration
            ssl_context = None
            if self.config.ssl:
                import ssl

                ssl_context = ssl.create_default_context(
                    cafile=self.config.ssl_ca_certs
                )
                if self.config.ssl_certfile and self.config.ssl_keyfile:
                    ssl_context.load_cert_chain(
                        certfile=self.config.ssl_certfile,
                        keyfile=self.config.ssl_keyfile,
                    )
                ssl_context.verify_mode = getattr(
                    ssl, f'CERT_{self.config.ssl_cert_reqs.upper()}', ssl.CERT_REQUIRED
                )

            # Build connection parameters
            connection_params = {
                'socket_timeout': self.config.socket_timeout,
                'socket_connect_timeout': self.config.socket_connect_timeout,
                'decode_responses': True,
                'max_connections': self.config.cluster_max_connections,
            }

            # Add SSL configuration
            if ssl_context:
                connection_params['ssl'] = ssl_context

            # Add authentication
            if self.config.enable_acl and self.config.username:
                connection_params['username'] = self.config.username
                connection_params['password'] = self.config.password
            elif self.config.password:
                connection_params['password'] = self.config.password

            # Create cluster client
            self._redis_client = RedisCluster(
                self.config.cluster_nodes,
                **connection_params,
            )
            logger.info(
                f'Connected to Redis Cluster with {len(self.config.cluster_nodes)} nodes'
            )

            self._key_prefix = self.config.key_prefix

            # Configure memory management
            self.configure_memory_management()

        except ImportError:
            logger.warning('Redis Cluster not available, falling back to regular Redis')
            self._init_redis_client()
        except Exception as e:
            logger.error(f'Failed to initialize Cluster client: {e}')
            self._init_redis_client()

    def _init_sentinel_client(self) -> None:
        """Initialize Redis Sentinel client for HA."""
        try:
            from redis.sentinel import Sentinel

            # Build SSL configuration
            ssl_context = None
            if self.config.ssl:
                import ssl

                ssl_context = ssl.create_default_context(
                    cafile=self.config.ssl_ca_certs
                )
                if self.config.ssl_certfile and self.config.ssl_keyfile:
                    ssl_context.load_cert_chain(
                        certfile=self.config.ssl_certfile,
                        keyfile=self.config.ssl_keyfile,
                    )
                ssl_context.verify_mode = getattr(
                    ssl, f'CERT_{self.config.ssl_cert_reqs.upper()}', ssl.CERT_REQUIRED
                )

            # Build connection parameters
            connection_params = {
                'socket_timeout': self.config.socket_timeout,
                'socket_connect_timeout': self.config.socket_connect_timeout,
                'decode_responses': True,
            }

            # Add SSL configuration
            if ssl_context:
                connection_params['ssl'] = ssl_context

            # Add authentication
            if self.config.enable_acl and self.config.username:
                connection_params['username'] = self.config.username
                connection_params['password'] = self.config.password
            elif self.config.password:
                connection_params['password'] = self.config.password

            # Create Sentinel client
            sentinel = Sentinel(
                self.config.sentinel_hosts,
                socket_timeout=self.config.sentinel_socket_timeout,
                **connection_params,
            )

            # Get master client
            self._redis_client = sentinel.master_for(self.config.sentinel_master_name)
            logger.info(
                f'Connected to Redis Sentinel master: {self.config.sentinel_master_name}'
            )

            self._key_prefix = self.config.key_prefix

            # Configure memory management
            self.configure_memory_management()

        except ImportError:
            logger.warning(
                'Redis Sentinel not available, falling back to regular Redis'
            )
            self._init_redis_client()
        except Exception as e:
            logger.error(f'Failed to initialize Sentinel client: {e}')
            self._init_redis_client()

    def _validate_network_access(self) -> None:
        """Validate that Redis host is in allowed networks."""
        import socket

        try:
            # Resolve hostname to IP
            hostname = self.config.host
            ip_address = socket.gethostbyname(hostname)

            # Check against allowed networks
            import ipaddress

            allowed = False
            for network in self.config.allowed_networks or []:
                try:
                    network_obj = ipaddress.ip_network(network)
                    if ipaddress.ip_address(ip_address) in network_obj:
                        allowed = True
                        break
                except ValueError as e:
                    logger.warning(f'Invalid network CIDR: {network}: {e}')

            if not allowed:
                raise SecurityError(
                    f'Redis host {hostname} ({ip_address}) not in allowed networks: {self.config.allowed_networks}'
                )

            logger.info(f'Network access validated: {hostname} in allowed networks')

        except socket.gaierror as e:
            logger.error(f'Failed to resolve hostname {self.config.host}: {e}')
            raise
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f'Network validation failed: {e}')
            raise

    def _get_from_cache(self, key: str) -> Optional[SubagentApprovalRequest]:
        """Get value from local cache if available and not expired."""
        if not self.config.enable_local_cache:
            return None

        cached = self._cache.get(key)
        if cached:
            request, timestamp = cached
            if time.time() - timestamp < self.config.cache_ttl_seconds:
                return request
            else:
                # Expired, remove from cache
                del self._cache[key]
        return None

    def _set_cache(self, key: str, request: SubagentApprovalRequest) -> None:
        """Set value in local cache."""
        if self.config.enable_local_cache:
            self._cache[key] = (request, time.time())

    def _clear_cache(self, key: Optional[str] = None) -> None:
        """Clear cache for a specific key or all cache."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def _track_slow_query(
        self,
        operation: str,
        duration_ms: float,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Track slow queries for monitoring.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            details: Additional details about the operation
        """
        if not self.config.enable_slow_query_log:
            return

        if duration_ms > self.config.slow_query_threshold_ms:
            self._slow_queries.append(
                {
                    'timestamp': time.time(),
                    'operation': operation,
                    'duration_ms': duration_ms,
                    'details': details or {},
                }
            )
            logger.warning(f'Slow query detected: {operation} took {duration_ms:.2f}ms')

    def get_slow_queries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent slow queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slow query records
        """
        return self._slow_queries[-limit:]

    def clear_slow_queries(self) -> None:
        """Clear slow query log."""
        self._slow_queries.clear()

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with connection stats
        """
        try:
            client_info = self.redis_client.info('clients')
            return {
                'total_operations': self._connection_stats['total_operations'],
                'failed_operations': self._connection_stats['failed_operations'],
                'slow_operations': self._connection_stats['slow_operations'],
                'connected_clients': client_info.get('connected_clients', 0),
                'blocked_clients': client_info.get('blocked_clients', 0),
            }
        except Exception as e:
            logger.error(f'Failed to get connection stats: {e}')
            return self._connection_stats

    def _execute_with_retry(
        self,
        operation: Callable[..., Any],
        operation_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute operation with retry logic.

        Args:
            operation: Operation to execute
            operation_name: Name of the operation for logging
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            Operation result
        """
        if not self.config.enable_retry:
            return operation(*args, **kwargs)

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                self._connection_stats['total_operations'] += 1
                return operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._connection_stats['failed_operations'] += 1
                logger.warning(
                    f'{operation_name} failed (attempt {attempt + 1}/{self.config.max_retries}): {e}'
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_ms / 1000)

        raise last_error

    def configure_memory_management(self) -> bool:
        """Configure Redis memory management settings.

        Returns:
            True if successful
        """
        if not self.config.enable_memory_management:
            return True

        try:
            # Set max memory if configured
            if self.config.max_memory_mb:
                self.redis_client.config_set(
                    'maxmemory', f'{self.config.max_memory_mb}mb'
                )
                logger.info(f'Set Redis max memory to {self.config.max_memory_mb}mb')

            # Set eviction policy
            self.redis_client.config_set(
                'maxmemory-policy', self.config.eviction_policy
            )
            logger.info(f'Set Redis eviction policy to {self.config.eviction_policy}')

            return True
        except Exception as e:
            logger.error(f'Failed to configure memory management: {e}')
            return False

    def get_memory_info(self) -> dict[str, Any]:
        """Get Redis memory information.

        Returns:
            Dictionary with memory stats
        """
        try:
            info = self.redis_client.info('memory')
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                'used_memory_rss': info.get('used_memory_rss', 0),
                'used_memory_rss_human': info.get('used_memory_rss_human', '0B'),
                'maxmemory': info.get('maxmemory', 0),
                'maxmemory_human': info.get('maxmemory_human', '0B'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
            }
        except Exception as e:
            logger.error(f'Failed to get memory info: {e}')
            return {}

    def cleanup_expired_keys(self) -> int:
        """Clean up expired keys from Redis.

        Returns:
            Number of keys cleaned up
        """
        try:
            # Scan for keys with approval queue prefix
            pattern = f'{self._key_prefix}:*'
            keys = []
            for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            # Check TTL and delete expired keys
            expired_count = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl in (-2, -1):  # Key does not exist or has no expiry
                    continue
                elif ttl <= 0:  # Key is expired
                    self.redis_client.delete(key)
                    expired_count += 1

            if expired_count > 0:
                logger.info(f'Cleaned up {expired_count} expired keys')

            return expired_count
        except Exception as e:
            logger.error(f'Failed to cleanup expired keys: {e}')
            return 0

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
        start_time = time.time()
        key = self._request_key(parent_run_id, request.request_id)
        data = request.to_dict()
        self.redis_client.hset(key, mapping=data)
        duration_ms = (time.time() - start_time) * 1000
        self._track_slow_query(
            'save_request',
            duration_ms,
            {'parent_run_id': parent_run_id, 'request_id': request.request_id},
        )

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
        start_time = time.time()
        cache_key = self._request_key(parent_run_id, request_id)

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Fetch from Redis
        data = self.redis_client.hgetall(cache_key)
        if not data:
            return None

        request = request_from_dict(data)
        self._set_cache(cache_key, request)
        duration_ms = (time.time() - start_time) * 1000
        self._track_slow_query(
            'get_request',
            duration_ms,
            {'parent_run_id': parent_run_id, 'request_id': request_id},
        )
        return request

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

        # Invalidate cache
        self._clear_cache(key)

        # Remove from pending set if no longer pending
        if status != ApprovalRequestStatus.PENDING:
            pending_key = self._pending_set_key(parent_run_id)
            self.redis_client.srem(pending_key, request_id)

        return True

    def batch_update_request_status(
        self,
        parent_run_id: str,
        request_ids: list[str],
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> dict[str, Any]:
        """Update multiple request statuses in a single pipeline.

        Args:
            parent_run_id: Parent run ID
            request_ids: List of request IDs to update
            status: New status
            reason: Denial reason (if denied)
            approved_by: Who approved the requests

        Returns:
            Dictionary with update results
        """
        results = {
            'updated': 0,
            'skipped': 0,
            'failed': 0,
        }

        if not self.config.enable_pipelining:
            # Fall back to individual updates
            for request_id in request_ids:
                if self.update_request_status(
                    parent_run_id,
                    request_id,
                    status,
                    reason=reason,
                    approved_by=approved_by,
                ):
                    results['updated'] += 1
                else:
                    results['skipped'] += 1
            return results

        # Use pipeline for batch updates
        try:
            pipeline = self.redis_client.pipeline()
            pending_key = self._pending_set_key(parent_run_id)

            now = datetime.now(timezone.utc).isoformat()
            updates = {'status': status.value}

            if status == ApprovalRequestStatus.APPROVED:
                updates['approved_at'] = now
                updates['approved_by'] = approved_by
            elif status == ApprovalRequestStatus.DENIED:
                updates['denied_at'] = now
                updates['denial_reason'] = reason or 'Denied by human'

            for request_id in request_ids:
                key = self._request_key(parent_run_id, request_id)
                pipeline.hset(key, mapping=updates)
                if status != ApprovalRequestStatus.PENDING:
                    pipeline.srem(pending_key, request_id)

            # Execute pipeline
            pipeline.execute()
            results['updated'] = len(request_ids)

            # Invalidate cache for all updated requests
            for request_id in request_ids:
                key = self._request_key(parent_run_id, request_id)
                self._clear_cache(key)

        except Exception as e:
            logger.error(f'Batch update failed: {e}')
            results['failed'] = len(request_ids)

        return results

    def get_pending_requests_optimized(
        self,
        parent_run_id: str,
    ) -> list[SubagentApprovalRequest]:
        """Get all pending requests using pipelining for optimization.

        This uses Redis pipelining to fetch all pending requests in fewer round-trips.

        Args:
            parent_run_id: Parent run ID

        Returns:
            List of pending requests
        """
        if not self.config.enable_pipelining:
            return self.get_pending_requests(parent_run_id)

        try:
            pending_key = self._pending_set_key(parent_run_id)
            request_ids = self.redis_client.smembers(pending_key)

            if not request_ids:
                return []

            # Use pipeline to fetch all requests
            pipeline = self.redis_client.pipeline()
            for request_id in request_ids:
                key = self._request_key(parent_run_id, request_id)
                pipeline.hgetall(key)

            results = pipeline.execute()

            # Parse results
            pending: list[SubagentApprovalRequest] = []
            for data in results:
                if data:
                    try:
                        request = request_from_dict(data)
                        pending.append(request)
                    except Exception as e:
                        logger.error(f'Failed to parse request: {e}')

            return pending

        except Exception as e:
            logger.error(f'Optimized get_pending_requests failed: {e}')
            # Fall back to regular implementation
            return self.get_pending_requests(parent_run_id)

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

    def get_all_requests(self) -> list[dict[str, Any]]:
        """Get all requests from all parent runs.

        Returns:
            List of all request dictionaries
        """
        all_requests: list[dict[str, Any]] = []
        parent_run_ids = self.list_parent_run_ids()

        for parent_run_id in parent_run_ids:
            request_ids = self.get_all_request_ids(parent_run_id)
            for request_id in request_ids:
                request = self.get_request(parent_run_id, request_id)
                if request:
                    all_requests.append(request.to_dict())

        return all_requests

    def exists(self, parent_run_id: str) -> bool:
        """Check if a parent run has any data in Redis."""
        all_key = self._all_requests_key(parent_run_id)
        return self.redis_client.exists(all_key) > 0
