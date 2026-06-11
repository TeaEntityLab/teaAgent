"""Hybrid approval queue store combining file-based and Redis backends."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import threading
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, cast

from cryptography.fernet import Fernet

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_metrics import (
    BackendType,
    MetricsContext,
    OperationType,
    get_metrics_collector,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
    RedisApprovalQueueStore,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueueStore,
    default_hmac_secret,
    request_from_dict,
)
from teaagent.subagents._circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from teaagent.subagents._feature_flags import FeatureFlags
from teaagent.subagents._prometheus_metrics import PrometheusMetricsExporter

logger = logging.getLogger(__name__)


@dataclass
class HybridApprovalQueueConfig:
    """Configuration for hybrid approval queue."""

    workspace_root: Path
    hmac_secret: Optional[str] = None
    redis_config: Optional[RedisApprovalQueueConfig] = None
    redis_primary: bool = True  # If True, Redis is primary for writes
    sync_interval_seconds: int = 60
    enable_fallback: bool = True  # Enable fallback to file if Redis fails
    enable_circuit_breaker: bool = True  # Enable circuit breaker for Redis calls
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    enable_dynamic_sync: bool = True  # Enable dynamic sync interval adjustment
    min_sync_interval_seconds: int = 10  # Minimum sync interval
    max_sync_interval_seconds: int = 300  # Maximum sync interval
    enable_compression: bool = False  # Enable compression for large payloads
    compression_threshold_bytes: int = 1024  # Compress payloads larger than this
    enable_deduplication: bool = True  # Enable request deduplication
    deduplication_window_seconds: int = 300  # Deduplication time window
    enable_ttl: bool = True  # Enable TTL for requests
    default_ttl_seconds: int = 3600  # Default TTL for requests
    enable_priority: bool = False  # Enable priority queue support
    enable_health_check: bool = True  # Enable health check endpoint
    enable_rate_limiting: bool = False  # Enable rate limiting per subagent
    rate_limit_requests_per_minute: int = 60  # Rate limit per subagent
    enable_audit_trail: bool = True  # Enable audit trail for requests
    enable_encryption: bool = False  # Enable encryption for sensitive data
    enable_archival: bool = False  # Enable archival of old requests
    archival_age_days: int = 30  # Age before archival
    feature_flags: Optional[FeatureFlags] = None  # Feature flags for gradual rollout
    correlation_id: Optional[str] = None  # Global correlation ID for this session
    enable_security_monitoring: bool = True  # Enable security event monitoring
    security_alert_threshold: int = 10  # Alert threshold for security events
    health_check_interval: int = 60  # Health check interval in seconds
    enable_analytics: bool = True  # Enable request analytics
    auto_timeout_pending_requests: bool = True  # Auto-timeout pending requests
    pending_request_timeout_seconds: int = 3600  # Timeout for pending requests (1 hour)
    enable_notifications: bool = True  # Enable notification system
    enable_approval_policies: bool = True  # Enable automatic approval policies
    enable_delegation: bool = True  # Enable approval delegation
    enable_escalation: bool = True  # Enable request escalation
    escalation_threshold_seconds: int = 7200  # Escalation threshold (2 hours)
    enable_comments: bool = True  # Enable request comments
    enable_approval_history: bool = True  # Enable approval history tracking
    enable_quota_management: bool = True  # Enable approval quota management
    default_approval_quota: int = 100  # Default approval quota per user
    enable_workflow_chains: bool = True  # Enable multi-step approval workflows
    enable_tagging: bool = True  # Enable request tagging
    enable_voting: bool = True  # Enable approval voting
    enable_reminders: bool = True  # Enable approval reminders
    enable_audit_reports: bool = True  # Enable audit report generation
    enable_sla_tracking: bool = True  # Enable SLA tracking
    default_sla_seconds: int = 86400  # Default SLA (24 hours)
    enable_conditions: bool = True  # Enable approval conditions
    enable_dependencies: bool = True  # Enable request dependencies
    enable_priority_escalation: bool = True  # Enable priority-based escalation
    enable_validation_rules: bool = True  # Enable validation rules
    enable_signatures: bool = True  # Enable approval signatures
    enable_versioning: bool = True  # Enable request versioning
    enable_conflict_resolution: bool = True  # Enable conflict resolution
    enable_performance_metrics: bool = True  # Enable performance metrics
    enable_compliance_checks: bool = True  # Enable compliance checks


class HybridApprovalQueueStore:
    """Hybrid approval queue combining file-based and Redis backends.

    Write Strategy:
    - If redis_primary=True: Write to Redis first, then file (backup)
    - If redis_primary=False: Write to file first, then Redis (backup)
    - Fallback: If primary fails, fall back to secondary

    Read Strategy:
    - Read from file (faster for read operations)
    - Optional: Read from Redis if file fails

    Sync Strategy:
    - Periodic sync between backends
    - On-demand sync for specific requests
    - Consistency validation
    """

    def __init__(
        self,
        config: HybridApprovalQueueConfig,
        file_store: Optional[ApprovalQueueStore] = None,
        redis_store: Optional[RedisApprovalQueueStore] = None,
    ) -> None:
        self.config = config
        self._file_store = file_store or ApprovalQueueStore(
            workspace_root=config.workspace_root,
            hmac_secret=config.hmac_secret or default_hmac_secret(),
        )
        self._redis_client: Optional[Any] = None
        self._redis_store: Optional[RedisApprovalQueueStore] = None

        if redis_store:
            self._redis_store = redis_store
        elif config.redis_config:
            self._redis_store = RedisApprovalQueueStore(config=config.redis_config)

        self._redis_available = self._check_redis_available()
        self._sync_errors = 0
        self._max_sync_errors = 5

        # Initialize circuit breaker for Redis calls
        self._circuit_breaker: Optional[CircuitBreaker] = None
        if config.enable_circuit_breaker and self._redis_store:
            self._circuit_breaker = CircuitBreaker(
                name='redis_approval_queue',
                config=config.circuit_breaker_config or CircuitBreakerConfig(),
            )
            logger.info('Circuit breaker enabled for Redis operations')

        # Initialize metrics
        self._metrics_collector = get_metrics_collector()
        self._metrics = self._metrics_collector.get_or_create_metrics(
            BackendType.HYBRID
        )

        # Deduplication tracking
        self._request_hashes: dict[str, float] = {}  # hash -> timestamp
        self._deduplication_lock: Optional[Any] = None

        # Rate limiting tracking
        self._rate_limit_tracker: defaultdict[str, list[float]] = defaultdict(
            list
        )  # subagent_id -> timestamps

        # Audit trail
        self._audit_trail: list[dict[str, Any]] = []

        # Security event monitoring
        self._security_events: list[dict[str, Any]] = []
        self._security_alerts: list[dict[str, Any]] = []

        # Prometheus metrics exporter
        self._prometheus_exporter = PrometheusMetricsExporter()

        # Thread safety lock for in-memory state
        self._state_lock = threading.RLock()

        # Helper context manager for thread-safe access
        self._lock = self._state_lock

        # Request analytics (lazy init)
        self._analytics: Optional[dict[str, Any]] = None

        # Notification system (lazy init)
        self._notifications: Optional[list[dict[str, Any]]] = None

        # Approval policies (always init, these are config-driven)
        self._approval_policies: dict[
            str, Callable[[SubagentApprovalRequest], bool]
        ] = {
            'auto_approve_safe_operations': self._policy_auto_approve_safe_operations,
            'auto_approve_low_risk_tools': self._policy_auto_approve_low_risk_tools,
        }

        # Delegation system (lazy init)
        self._delegations: Optional[dict[str, dict[str, Any]]] = None

        # Escalation system (lazy init)
        self._escalations: Optional[dict[str, dict[str, Any]]] = None

        # Comments system (lazy init)
        self._comments: Optional[dict[str, list[dict[str, Any]]]] = None

        # Approval history (lazy init)
        self._approval_history: Optional[dict[str, list[dict[str, Any]]]] = None

        # Quota management (always init, needed for quota checks)
        self._approval_quotas: dict[str, int] = {}
        self._approval_counts: dict[str, int] = {}

        # Workflow chains (always init, config-driven)
        self._workflow_chains: dict[str, list[str]] = {}

        # Reviewer assignment (lazy init)
        self._reviewer_assignments: Optional[dict[str, str]] = None

        # Approval templates (always init, config-driven)
        self._approval_templates: dict[str, dict[str, Any]] = {}

        # Request tags (lazy init)
        self._request_tags: Optional[dict[str, set[str]]] = None

        # Voting system (lazy init)
        self._votes: Optional[dict[str, dict[str, bool]]] = None

        # Reminder system (lazy init)
        self._reminders: Optional[dict[str, list[float]]] = None

        # SLA tracking (lazy init)
        self._sla_deadlines: Optional[dict[str, float]] = None

        # Approval conditions (always init, config-driven)
        self._approval_conditions: dict[
            str, Callable[[SubagentApprovalRequest], bool]
        ] = {}

        # Request dependencies (lazy init)
        self._dependencies: Optional[dict[str, list[str]]] = None

        # Priority escalation (always init, config-driven)
        self._priority_escalation_rules: dict[str, int] = {}

        # Validation rules (always init, config-driven)
        self._validation_rules: dict[
            str, Callable[[SubagentApprovalRequest], tuple[bool, str]]
        ] = {}

        # Signatures (lazy init)
        self._signatures: Optional[dict[str, dict[str, Any]]] = None

        # Versioning (lazy init)
        self._versions: Optional[dict[str, list[dict[str, Any]]]] = None

        # Conflict resolution (lazy init)
        self._conflicts: Optional[dict[str, dict[str, Any]]] = None

        # Performance metrics (lazy init)
        self._performance_metrics: Optional[dict[str, dict[str, float]]] = None

        # Compliance checks (always init, config-driven)
        self._compliance_rules: dict[
            str, Callable[[SubagentApprovalRequest], tuple[bool, str]]
        ] = {}

        # Encryption
        self._encryption_key: Optional[bytes] = None
        self._cipher: Optional[Fernet] = None
        if config.enable_encryption:
            self._encryption_key = Fernet.generate_key()
            self._cipher = Fernet(self._encryption_key)
            logger.info('Encryption enabled for sensitive data')

        # Load persisted state on init
        self._load_state_from_file()

        # Lazy initialization helpers
        self._init_analytics()
        self._init_notifications()

        # Dynamic sync state
        self._current_sync_interval = config.sync_interval_seconds
        self._last_sync_time: float = 0
        self._operation_latencies: list[float] = []
        self._max_latency_samples = 100

        # Feature flags for gradual rollout
        self._feature_flags = config.feature_flags or FeatureFlags()

    def _init_analytics(self) -> None:
        """Initialize analytics if enabled and not yet initialized."""
        if self.config.enable_analytics and self._analytics is None:
            self._analytics = {
                'total_requests': 0,
                'approved_requests': 0,
                'denied_requests': 0,
                'cancelled_requests': 0,
                'pending_requests': 0,
                'by_subagent': {},
                'by_tool': {},
                'approval_rate': 0.0,
                'average_approval_time_seconds': 0.0,
            }

    def _init_notifications(self) -> None:
        """Initialize notifications if enabled and not yet initialized."""
        if self.config.enable_notifications and self._notifications is None:
            self._notifications = []

    def _ensure_analytics(self) -> None:
        """Ensure analytics is initialized."""
        if self._analytics is None:
            self._init_analytics()

    def _ensure_notifications(self) -> None:
        """Ensure notifications is initialized."""
        if self._notifications is None:
            self._init_notifications()

    def _ensure_comments(self) -> None:
        """Ensure comments is initialized."""
        if self._comments is None:
            self._comments = {}

    def _ensure_votes(self) -> None:
        """Ensure votes is initialized."""
        if self._votes is None:
            self._votes = {}

    def _ensure_tags(self) -> None:
        """Ensure tags is initialized."""
        if self._request_tags is None:
            self._request_tags = {}

    def _ensure_dependencies(self) -> None:
        """Ensure dependencies is initialized."""
        if self._dependencies is None:
            self._dependencies = {}

    def _ensure_sla_deadlines(self) -> None:
        """Ensure SLA deadlines is initialized."""
        if self._sla_deadlines is None:
            self._sla_deadlines = {}

    def _ensure_signatures(self) -> None:
        """Ensure signatures is initialized."""
        if self._signatures is None:
            self._signatures = {}

    def _ensure_versions(self) -> None:
        """Ensure versions is initialized."""
        if self._versions is None:
            self._versions = {}

    def _ensure_conflicts(self) -> None:
        """Ensure conflicts is initialized."""
        if self._conflicts is None:
            self._conflicts = {}

    def _ensure_performance_metrics(self) -> None:
        """Ensure performance metrics is initialized."""
        if self._performance_metrics is None:
            self._performance_metrics = {}

    def _ensure_approval_history(self) -> None:
        """Ensure approval history is initialized."""
        if self._approval_history is None:
            self._approval_history = {}

    def _ensure_delegations(self) -> None:
        """Ensure delegations is initialized."""
        if self._delegations is None:
            self._delegations = {}

    def _ensure_escalations(self) -> None:
        """Ensure escalations is initialized."""
        if self._escalations is None:
            self._escalations = {}

    def _ensure_reviewer_assignments(self) -> None:
        """Ensure reviewer assignments is initialized."""
        if self._reviewer_assignments is None:
            self._reviewer_assignments = {}

    def _ensure_reminders(self) -> None:
        """Ensure reminders is initialized."""
        if self._reminders is None:
            self._reminders = {}

    def should_use_hybrid_queue(self, request_id: str) -> bool:
        """Check if a request should use the hybrid queue based on feature flags.

        Args:
            request_id: Request ID to use for consistent hashing

        Returns:
            True if request should use hybrid queue, False otherwise
        """
        return self._feature_flags.should_use_hybrid_queue(request_id)

    def pre_migration_validation(self) -> dict[str, Any]:
        """Validate system state before migration.

        Returns:
            Dictionary with validation results
        """
        validation: dict[str, Any] = {
            'timestamp': time.time(),
            'checks': [],
            'overall_status': False,
        }

        checks = []

        # Check file store operations
        try:
            test_parent_run_id = 'pre-migration-test'
            test_request = SubagentApprovalRequest(
                request_id='test-request-id',
                subagent_id='test-subagent',
                parent_run_id=test_parent_run_id,
                subagent_name='test-subagent-name',
                tool_name='test_tool',
                tool_arguments={'test': 'data'},
                permission_mode='read',
                isolation='none',
            )
            self._file_store.save(
                test_parent_run_id, {test_request.request_id: test_request}, {}
            )
            loaded = self._file_store.load(test_parent_run_id)
            checks.append(
                ('File save operation', loaded.parent_run_id == test_parent_run_id)
            )
        except Exception as e:
            checks.append(('File save operation', False, str(e)))

        # Check file read operation
        try:
            snapshot = self._file_store.load(test_parent_run_id)
            checks.append(
                ('File read operation', snapshot.parent_run_id == test_parent_run_id)
            )
        except Exception as e:
            checks.append(('File read operation', False, str(e)))

        # Check Redis operations if available
        if self._redis_store:
            try:
                self._redis_store.save_request(test_parent_run_id, test_request)
                loaded = self._redis_store.get_request(
                    test_parent_run_id, test_request.request_id
                )
                checks.append(('Redis save operation', loaded is not None))
            except Exception as e:
                checks.append(('Redis save operation', False, str(e)))

            try:
                loaded = self._redis_store.get_request(
                    test_parent_run_id, test_request.request_id
                )
                checks.append(('Redis read operation', loaded is not None))
            except Exception as e:
                checks.append(('Redis read operation', False, str(e)))

        # Check consistency between backends
        if self._redis_store:
            try:
                consistency = self.validate_global_consistency()
                checks.append(
                    ('Backend consistency', consistency['consistency_rate'] > 0.99)
                )
            except Exception as e:
                checks.append(('Backend consistency', False, str(e)))

        # Cleanup test data
        try:
            self._file_store.delete(test_parent_run_id)
            if self._redis_store:
                self._redis_store.delete(test_parent_run_id)
        except Exception as e:
            logger.warning(f'Cleanup failed: {e}')

        validation['checks'] = checks
        validation['overall_status'] = all(check[1] for check in checks)

        return validation

    def post_migration_validation(self) -> dict[str, Any]:
        """Validate system state after migration.

        Returns:
            Dictionary with validation results
        """
        validation: dict[str, Any] = {
            'timestamp': time.time(),
            'checks': [],
            'overall_status': False,
        }

        checks = []

        # Check submit operation
        try:
            test_parent_run_id = 'post-migration-test'
            test_request = SubagentApprovalRequest(
                request_id='test-request-id',
                subagent_id='test-subagent',
                parent_run_id=test_parent_run_id,
                subagent_name='test-subagent-name',
                tool_name='test_tool',
                tool_arguments={'test': 'data'},
                permission_mode='read',
                isolation='none',
            )
            self.save_request(test_parent_run_id, test_request)
            checks.append(('Submit operation', True))
        except Exception as e:
            checks.append(('Submit operation', False, str(e)))

        # Check approve operation
        try:
            self.update_request_status(
                test_parent_run_id,
                test_request.request_id,
                ApprovalRequestStatus.APPROVED,
            )
            checks.append(('Approve operation', True))
        except Exception as e:
            checks.append(('Approve operation', False, str(e)))

        # Check read operation
        try:
            pending = self.get_pending_requests(test_parent_run_id)
            checks.append(('Read operation', isinstance(pending, list)))
        except Exception as e:
            checks.append(('Read operation', False, str(e)))

        # Check consistency
        try:
            consistency = self.validate_global_consistency()
            checks.append(('Consistency', consistency['consistency_rate'] > 0.99))
        except Exception as e:
            checks.append(('Consistency', False, str(e)))

        # Cleanup test data
        try:
            self.delete(test_parent_run_id)
        except Exception as e:
            logger.warning(f'Cleanup failed: {e}')

        validation['checks'] = checks
        validation['overall_status'] = all(check[1] for check in checks)

        return validation

    def validate_migration(
        self, source: str = 'file', destination: str = 'redis'
    ) -> dict[str, Any]:
        """Validate data migration between backends.

        Args:
            source: Source backend ('file' or 'redis')
            destination: Destination backend ('file' or 'redis')

        Returns:
            Dictionary with validation results
        """
        validation: dict[str, Any] = {
            'timestamp': time.time(),
            'source': source,
            'destination': destination,
            'checks': [],
            'overall_status': False,
        }

        checks = []

        # Get counts from both backends
        try:
            if source == 'file':
                source_count = len(self._file_store.get_all_requests())
            else:
                source_count = len(self._redis_store.get_all_requests())

            if destination == 'file':
                dest_count = len(self._file_store.get_all_requests())
            else:
                dest_count = len(self._redis_store.get_all_requests())

            checks.append(
                (
                    'Count match',
                    source_count == dest_count,
                    f'{source_count} vs {dest_count}',
                )
            )
        except Exception as e:
            checks.append(('Count match', False, str(e)))

        # Validate consistency
        try:
            consistency = self.validate_global_consistency()
            checks.append(
                (
                    'Consistency',
                    consistency['consistency_rate'] > 0.99,
                    f'{consistency["consistency_rate"]:.2%}',
                )
            )
        except Exception as e:
            checks.append(('Consistency', False, str(e)))

        validation['checks'] = checks
        validation['overall_status'] = all(check[1] for check in checks)

        return validation

    def validate_global_consistency(self) -> dict[str, Any]:
        """Validate consistency between Redis and file backends globally.

        Returns:
            Dictionary with consistency metrics and details
        """
        consistency_report: dict[str, Any] = {
            'timestamp': time.time(),
            'redis_available': self._redis_available,
            'file_available': True,
            'total_redis_requests': 0,
            'total_file_requests': 0,
            'missing_in_redis': 0,
            'missing_in_file': 0,
            'inconsistent_requests': 0,
            'consistency_rate': 0.0,
            'details': [],
        }

        try:
            if not self._redis_store:
                consistency_report['redis_available'] = False
                consistency_report['details'].append('Redis store not available')
                return consistency_report

            # Get all request IDs from both backends
            redis_request_ids: set[str] = set()
            file_request_ids: set[str] = set()

            # Get Redis request IDs
            redis_parent_runs = self._redis_store.list_parent_run_ids()
            for parent_run_id in redis_parent_runs:
                try:
                    request_ids = self._redis_store.get_all_request_ids(parent_run_id)
                    redis_request_ids.update(request_ids)
                except Exception as e:
                    consistency_report['details'].append(
                        f'Failed to get Redis requests for {parent_run_id}: {e}'
                    )

            # Get file request IDs
            file_parent_runs = self._file_store.list_parent_run_ids()
            for parent_run_id in file_parent_runs:
                try:
                    snapshot = self._file_store.load(parent_run_id)
                    file_request_ids.update(snapshot.requests.keys())
                except Exception as e:
                    consistency_report['details'].append(
                        f'Failed to get file requests for {parent_run_id}: {e}'
                    )

            consistency_report['total_redis_requests'] = len(redis_request_ids)
            consistency_report['total_file_requests'] = len(file_request_ids)

            # Find missing requests
            missing_in_redis = file_request_ids - redis_request_ids
            missing_in_file = redis_request_ids - file_request_ids

            consistency_report['missing_in_redis'] = len(missing_in_redis)
            consistency_report['missing_in_file'] = len(missing_in_file)

            # Check for inconsistent request data
            common_requests = redis_request_ids & file_request_ids
            inconsistent_count = 0

            # Note: Full data consistency check would require comparing request data
            # For now, we just check for missing requests
            consistency_report['inconsistent_requests'] = inconsistent_count

            # Calculate consistency rate
            total_unique = len(redis_request_ids | file_request_ids)
            if total_unique > 0:
                matching = len(common_requests)
                consistency_report['consistency_rate'] = matching / total_unique
            else:
                consistency_report['consistency_rate'] = 1.0

            # Add details
            if missing_in_redis:
                consistency_report['details'].append(
                    f'{len(missing_in_redis)} requests missing in Redis'
                )
            if missing_in_file:
                consistency_report['details'].append(
                    f'{len(missing_in_file)} requests missing in file'
                )
            if consistency_report['consistency_rate'] < 0.99:
                consistency_report['details'].append(
                    f'Consistency rate below 99%: {consistency_report["consistency_rate"]:.2%}'
                )

        except Exception as e:
            logger.error(f'Consistency validation failed: {e}')
            consistency_report['error'] = str(e)

        return consistency_report

    def _adjust_sync_interval(self, operation_latency: float) -> None:
        """Dynamically adjust sync interval based on operation latency.

        Args:
            operation_latency: Latency of the last operation in seconds
        """
        if not self.config.enable_dynamic_sync:
            return

        # Add latency to samples
        self._operation_latencies.append(operation_latency)
        if len(self._operation_latencies) > self._max_latency_samples:
            self._operation_latencies.pop(0)

        # Calculate average latency
        if len(self._operation_latencies) < 10:
            return  # Need more samples

        avg_latency = sum(self._operation_latencies) / len(self._operation_latencies)

        # Adjust sync interval based on latency
        # Higher latency -> longer sync interval to reduce load
        # Lower latency -> shorter sync interval for better consistency
        if avg_latency > 1.0:  # High latency
            target_interval = min(
                self._current_sync_interval * 1.5, self.config.max_sync_interval_seconds
            )
        elif avg_latency > 0.5:  # Medium latency
            target_interval = min(
                self._current_sync_interval * 1.1, self.config.max_sync_interval_seconds
            )
        elif avg_latency < 0.1:  # Low latency
            target_interval = max(
                self._current_sync_interval * 0.9, self.config.min_sync_interval_seconds
            )
        else:
            target_interval = self._current_sync_interval

        # Apply change gradually
        self._current_sync_interval = int(target_interval)

        logger.debug(
            f'Adjusted sync interval to {self._current_sync_interval}s '
            f'(avg latency: {avg_latency:.3f}s)'
        )

    def get_current_sync_interval(self) -> int:
        """Get the current sync interval.

        Returns:
            Current sync interval in seconds
        """
        return self._current_sync_interval

    def _check_redis_available(self) -> bool:
        """Check if Redis is available."""
        if self._redis_store is None:
            return False
        try:
            return self._redis_store.ping()
        except Exception as e:
            logger.warning(f'Redis not available: {e}')
            return False

    @property
    def redis_available(self) -> bool:
        """Check if Redis is available."""
        return self._redis_available

    @property
    def file_store(self) -> ApprovalQueueStore:
        """Get the file store."""
        return self._file_store

    @property
    def redis_store(self) -> Optional[RedisApprovalQueueStore]:
        """Get the Redis store."""
        return self._redis_store

    def _call_redis(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute Redis call with circuit breaker protection."""
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(func, *args, **kwargs)
            except Exception as e:
                logger.warning(f'Circuit breaker blocked Redis call: {e}')
                self._redis_available = False
                raise
        else:
            return func(*args, **kwargs)

    def get_circuit_breaker_stats(self) -> Optional[dict]:
        """Get circuit breaker statistics."""
        if self._circuit_breaker:
            return self._circuit_breaker.get_stats()
        return None

    def bulk_approve_requests(
        self,
        parent_run_id: str,
        request_ids: list[str],
        approved_by: str = 'human',
    ) -> dict[str, Any]:
        """Approve multiple requests in bulk.

        Args:
            parent_run_id: Parent run ID
            request_ids: List of request IDs to approve
            approved_by: Who approved the requests

        Returns:
            Dictionary with approval results
        """
        results = {
            'approved': 0,
            'failed': 0,
            'errors': [],
        }

        for request_id in request_ids:
            try:
                success = self.update_request_status(
                    parent_run_id,
                    request_id,
                    ApprovalRequestStatus.APPROVED,
                    approved_by=approved_by,
                )
                if success:
                    results['approved'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f'Failed to approve {request_id}')
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f'{request_id}: {str(e)}')

        return results

    def bulk_deny_requests(
        self,
        parent_run_id: str,
        request_ids: list[str],
        reason: str = 'Bulk denied',
        approved_by: str = 'human',
    ) -> dict[str, Any]:
        """Deny multiple requests in bulk.

        Args:
            parent_run_id: Parent run ID
            request_ids: List of request IDs to deny
            reason: Denial reason
            approved_by: Who denied the requests

        Returns:
            Dictionary with denial results
        """
        results = {
            'denied': 0,
            'failed': 0,
            'errors': [],
        }

        for request_id in request_ids:
            try:
                success = self.update_request_status(
                    parent_run_id,
                    request_id,
                    ApprovalRequestStatus.DENIED,
                    reason=reason,
                    approved_by=approved_by,
                )
                if success:
                    results['denied'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f'Failed to deny {request_id}')
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f'{request_id}: {str(e)}')

        return results

    def _persist_state_to_file(self) -> bool:
        """Persist in-memory state to file store.

        Returns:
            True if successful
        """
        try:
            state = {
                'analytics': self._analytics,
                'notifications': self._notifications,
                'delegations': self._delegations,
                'escalations': self._escalations,
                'comments': self._comments,
                'approval_history': self._approval_history,
                'approval_quotas': self._approval_quotas,
                'approval_counts': self._approval_counts,
                'workflow_chains': self._workflow_chains,
                'reviewer_assignments': self._reviewer_assignments,
                'approval_templates': self._approval_templates,
                'request_tags': {
                    k: list(v) for k, v in (self._request_tags or {}).items()
                },
                'votes': self._votes,
                'reminders': self._reminders,
                'sla_deadlines': self._sla_deadlines,
                'dependencies': self._dependencies,
                'priority_escalation_rules': self._priority_escalation_rules,
                'signatures': self._signatures,
                'versions': self._versions,
                'conflicts': self._conflicts,
                'performance_metrics': self._performance_metrics,
            }

            # Save to a special state file in workspace
            state_file = self.config.workspace_root / '.hybrid_queue_state.json'
            with open(state_file, 'w') as f:
                json.dump(state, f, default=str)

            logger.info('Persisted in-memory state to file')
            return True

        except Exception as e:
            logger.error(f'Failed to persist state: {e}')
            return False

    def _load_state_from_file(self) -> bool:
        """Load in-memory state from file store.

        Returns:
            True if successful
        """
        try:
            state_file = self.config.workspace_root / '.hybrid_queue_state.json'
            if not state_file.exists():
                return False

            with open(state_file, 'r') as f:
                state = json.load(f)

            with self._lock:
                if 'analytics' in state:
                    self._analytics = state['analytics']
                if 'notifications' in state:
                    self._notifications = state['notifications']
                if 'delegations' in state:
                    self._delegations = state['delegations']
                if 'escalations' in state:
                    self._escalations = state['escalations']
                if 'comments' in state:
                    self._comments = state['comments']
                if 'approval_history' in state:
                    self._approval_history = state['approval_history']
                if 'approval_quotas' in state:
                    self._approval_quotas = state['approval_quotas']
                if 'approval_counts' in state:
                    self._approval_counts = state['approval_counts']
                if 'workflow_chains' in state:
                    self._workflow_chains = state['workflow_chains']
                if 'reviewer_assignments' in state:
                    self._reviewer_assignments = state['reviewer_assignments']
                if 'approval_templates' in state:
                    self._approval_templates = state['approval_templates']
                if 'request_tags' in state:
                    self._request_tags = {
                        k: set(v) for k, v in state['request_tags'].items()
                    }
                if 'votes' in state:
                    self._votes = state['votes']
                if 'reminders' in state:
                    self._reminders = state['reminders']
                if 'sla_deadlines' in state:
                    self._sla_deadlines = state['sla_deadlines']
                if 'dependencies' in state:
                    self._dependencies = state['dependencies']
                if 'priority_escalation_rules' in state:
                    self._priority_escalation_rules = state['priority_escalation_rules']
                if 'signatures' in state:
                    self._signatures = state['signatures']
                if 'versions' in state:
                    self._versions = state['versions']
                if 'conflicts' in state:
                    self._conflicts = state['conflicts']
                if 'performance_metrics' in state:
                    self._performance_metrics = state['performance_metrics']

            logger.info('Loaded in-memory state from file')
            return True

        except Exception as e:
            logger.error(f'Failed to load state: {e}')
            return False

    def escalate_overdue_requests(self) -> dict[str, Any]:
        """Escalate overdue pending requests.

        Returns:
            Dictionary with escalation results
        """
        if not self.config.enable_sla_tracking or not self.config.enable_escalation:
            return {'enabled': False}

        self._ensure_sla_deadlines()
        self._ensure_escalations()

        results = {
            'enabled': True,
            'escalated_count': 0,
            'skipped_count': 0,
            'errors': [],
        }

        try:
            current_time = time.time()

            for request_id, deadline in self._sla_deadlines.items():
                if current_time > deadline:
                    # Request is overdue, escalate it
                    escalation_info = {
                        'request_id': request_id,
                        'deadline': deadline,
                        'overdue_by': current_time - deadline,
                        'escalated_at': current_time,
                        'escalation_level': 1,
                    }

                    self._escalations[request_id] = escalation_info

                    self._create_notification(
                        'request_escalated',
                        f'Request {request_id} escalated due to SLA breach (overdue by {int(current_time - deadline)}s)',
                        request_id=request_id,
                        severity='warning',
                    )

                    results['escalated_count'] += 1
                    logger.warning(f'Escalated overdue request {request_id}')
                else:
                    results['skipped_count'] += 1

        except Exception as e:
            logger.error(f'Failed to escalate overdue requests: {e}')
            results['errors'].append(str(e))

        return results

    def timeout_pending_requests(self) -> dict[str, Any]:
        """Timeout pending requests that have exceeded the timeout threshold.

        Returns:
            Dictionary with timeout results
        """
        if not self.config.auto_timeout_pending_requests:
            return {'timed_out': 0, 'skipped': 'Auto-timeout disabled'}

        results = {
            'timed_out': 0,
            'failed': 0,
            'errors': [],
        }

        try:
            parent_run_ids = self.list_parent_run_ids()
            current_time = time.time()

            for parent_run_id in parent_run_ids:
                try:
                    pending = self.get_pending_requests(parent_run_id)
                    for request in pending:
                        # Check if request has timed out
                        request_age = current_time - request.created_at.timestamp()
                        if request_age > self.config.pending_request_timeout_seconds:
                            try:
                                self.update_request_status(
                                    parent_run_id,
                                    request.request_id,
                                    ApprovalRequestStatus.DENIED,
                                    reason=f'Auto-timed out after {request_age:.0f} seconds',
                                    approved_by='system',
                                )
                                results['timed_out'] += 1
                                logger.info(
                                    f'Timed out request {request.request_id} after {request_age:.0f} seconds'
                                )
                            except Exception as e:
                                results['failed'] += 1
                                results['errors'].append(
                                    f'{request.request_id}: {str(e)}'
                                )
                except Exception as e:
                    results['errors'].append(
                        f'Failed to process {parent_run_id}: {str(e)}'
                    )

        except Exception as e:
            logger.error(f'Failed to timeout pending requests: {e}')
            results['errors'].append(f'Overall error: {str(e)}')

        return results

    def trigger_rollback(self, reason: str) -> dict[str, Any]:
        """Trigger rollback to file-based queue.

        Args:
            reason: Reason for rollback

        Returns:
            Dictionary with rollback status and details
        """
        logger.warning(f'Rollback triggered: {reason}')

        self._record_security_event(
            'rollback_triggered',
            'high',
            {'reason': reason, 'correlation_id': self.config.correlation_id},
        )

        rollback_details: dict[str, Any] = {
            'reason': reason,
            'timestamp': time.time(),
            'steps': [],
            'success': False,
        }

        try:
            # Step 1: Stop all writes to Redis
            rollback_details['steps'].append(
                {'step': 'stop_redis_writes', 'status': 'in_progress'}
            )
            self._redis_available = False
            rollback_details['steps'].append(
                {'step': 'stop_redis_writes', 'status': 'completed'}
            )

            # Step 2: Sync Redis state to file
            rollback_details['steps'].append(
                {'step': 'sync_redis_to_file', 'status': 'in_progress'}
            )
            if self._redis_store:
                try:
                    redis_requests = self._redis_store.get_all_requests()
                    synced_count = 0
                    # Group requests by parent_run_id
                    requests_by_parent: dict[str, list[dict]] = {}
                    for request_dict in redis_requests:
                        parent_run_id = request_dict.get('parent_run_id')
                        if parent_run_id:
                            if parent_run_id not in requests_by_parent:
                                requests_by_parent[parent_run_id] = []
                            requests_by_parent[parent_run_id].append(request_dict)

                    # Sync each parent run's requests
                    for parent_run_id, request_dicts in requests_by_parent.items():
                        try:
                            # Load existing snapshot
                            snapshot = self._file_store.load(parent_run_id)
                            # Merge requests
                            requests = dict(snapshot.requests)
                            for request_dict in request_dicts:
                                request_id = request_dict.get('request_id')
                                if request_id:
                                    requests[request_id] = request_dict
                                    synced_count += 1
                            # Convert to SubagentApprovalRequest objects
                            request_objects: dict[str, SubagentApprovalRequest] = {}
                            for rid, rdict in requests.items():
                                with contextlib.suppress(Exception):
                                    request_objects[rid] = request_from_dict(rdict)
                            # Save updated snapshot
                            self._file_store.save(parent_run_id, request_objects, {})
                        except Exception as e:
                            logger.error(
                                f'Failed to sync parent run {parent_run_id}: {e}'
                            )

                    rollback_details['steps'].append(
                        {
                            'step': 'sync_redis_to_file',
                            'status': 'completed',
                            'synced_count': synced_count,
                        }
                    )
                except Exception as e:
                    logger.error(f'Failed to sync Redis to file: {e}')
                    rollback_details['steps'].append(
                        {
                            'step': 'sync_redis_to_file',
                            'status': 'failed',
                            'error': str(e),
                        }
                    )
            else:
                rollback_details['steps'].append(
                    {
                        'step': 'sync_redis_to_file',
                        'status': 'skipped',
                        'reason': 'no_redis_store',
                    }
                )

            # Step 3: Validate file state
            rollback_details['steps'].append(
                {'step': 'validate_file_state', 'status': 'in_progress'}
            )
            file_requests = self._file_store.get_all_requests()
            rollback_details['steps'].append(
                {
                    'step': 'validate_file_state',
                    'status': 'completed',
                    'file_request_count': len(file_requests),
                }
            )

            # Step 4: Switch to file-based queue
            rollback_details['steps'].append(
                {'step': 'switch_to_file_only', 'status': 'in_progress'}
            )
            self.config.redis_primary = False
            rollback_details['steps'].append(
                {'step': 'switch_to_file_only', 'status': 'completed'}
            )

            # Step 5: Validate operations
            rollback_details['steps'].append(
                {'step': 'validate_operations', 'status': 'in_progress'}
            )
            validation_result = self._validate_rollback()
            rollback_details['steps'].append(
                {
                    'step': 'validate_operations',
                    'status': 'completed',
                    'validation': validation_result,
                }
            )

            rollback_details['success'] = True
            logger.info('Rollback completed successfully')

        except Exception as e:
            logger.error(f'Rollback failed: {e}')
            rollback_details['success'] = False
            rollback_details['error'] = str(e)

        return rollback_details

    def _validate_rollback(self) -> dict:
        """Validate that rollback was successful.

        Returns:
            Dictionary with validation results
        """
        validation = {
            'save_operation': False,
            'load_operation': False,
            'list_operation': False,
            'overall': False,
        }

        try:
            # Test save operation
            test_parent_run_id = 'test-rollback-validation'
            test_request = SubagentApprovalRequest(
                request_id='test-request-id',
                subagent_id='test-subagent',
                parent_run_id=test_parent_run_id,
                subagent_name='test-subagent-name',
                tool_name='test_tool',
                tool_arguments={'test': 'data'},
                permission_mode='read',
                isolation='none',
            )
            self._file_store.save(
                test_parent_run_id, {test_request.request_id: test_request}, {}
            )
            validation['save_operation'] = True

            # Test load operation
            snapshot = self._file_store.load(test_parent_run_id)
            validation['load_operation'] = snapshot.parent_run_id == test_parent_run_id

            # Test list operation
            parent_run_ids = self._file_store.list_parent_run_ids()
            validation['list_operation'] = test_parent_run_id in parent_run_ids

            # Cleanup test data
            try:
                test_queue_path = self._file_store.queue_path(test_parent_run_id)
                if test_queue_path.exists():
                    test_queue_path.unlink()
            except Exception:
                pass

            validation['overall'] = all(validation.values())

        except Exception as e:
            logger.error(f'Rollback validation failed: {e}')
            validation['error'] = str(e)  # type: ignore[assignment]

        return validation

    def migrate_existing_data(
        self, source: str = 'file', destination: str = 'redis'
    ) -> dict[str, Any]:
        """Migrate existing approval queue data between backends.

        Args:
            source: Source backend ('file' or 'redis')
            destination: Destination backend ('file' or 'redis')

        Returns:
            Dictionary with migration status and details
        """
        migration_details: dict[str, Any] = {
            'source': source,
            'destination': destination,
            'timestamp': time.time(),
            'migrated_count': 0,
            'failed_count': 0,
            'success': False,
        }

        try:
            if source == 'file' and destination == 'redis':
                # Migrate from file to Redis
                if not self._redis_store:
                    migration_details['error'] = 'Redis store not available'
                    return migration_details

                file_requests = self._file_store.get_all_requests()
                migrated = 0
                failed = 0

                for request_dict in file_requests:
                    try:
                        request = request_from_dict(request_dict)
                        parent_run_id = request.parent_run_id
                        self._redis_store.save_request(parent_run_id, request)
                        migrated += 1
                    except Exception as e:
                        logger.error(
                            f'Migration failed for request {request_dict.get("request_id")}: {e}'
                        )
                        failed += 1

                migration_details['migrated_count'] = migrated
                migration_details['failed_count'] = failed
                migration_details['success'] = True

            elif source == 'redis' and destination == 'file':
                # Migrate from Redis to file
                if not self._redis_store:
                    migration_details['error'] = 'Redis store not available'
                    return migration_details

                redis_requests = self._redis_store.get_all_requests()
                migrated = 0
                failed = 0

                # Group requests by parent_run_id
                requests_by_parent: dict[str, list[dict[str, Any]]] = {}
                for request_dict in redis_requests:
                    parent_run_id = request_dict.get('parent_run_id')
                    if parent_run_id and isinstance(parent_run_id, str):
                        if parent_run_id not in requests_by_parent:
                            requests_by_parent[parent_run_id] = []
                        requests_by_parent[parent_run_id].append(request_dict)  # type: ignore[arg-type, assignment, list-item]

                # Migrate each parent run's requests
                for parent_run_id, request_dicts in requests_by_parent.items():
                    try:
                        snapshot = self._file_store.load(parent_run_id)
                        requests = dict(snapshot.requests)
                        for request_dict in request_dicts:
                            request_id = request_dict.get('request_id')
                            if request_id:
                                requests[request_id] = request_dict
                                migrated += 1
                        # Convert to SubagentApprovalRequest objects
                        request_objects: dict[str, SubagentApprovalRequest] = {}
                        for rid, rdict in requests.items():
                            with contextlib.suppress(Exception):
                                request_objects[rid] = request_from_dict(rdict)
                        self._file_store.save(parent_run_id, request_objects, {})
                    except Exception as e:
                        logger.error(
                            f'Migration failed for parent run {parent_run_id}: {e}'
                        )
                        failed += 1

                migration_details['migrated_count'] = migrated
                migration_details['failed_count'] = failed
                migration_details['success'] = True

            else:
                migration_details['error'] = (
                    f'Invalid migration path: {source} -> {destination}'
                )

        except Exception as e:
            logger.error(f'Migration failed: {e}')
            migration_details['error'] = str(e)
            migration_details['success'] = False

        return migration_details

    def incremental_migration(
        self, batch_size: int = 100, source: str = 'file', destination: str = 'redis'
    ) -> dict[str, Any]:  # type: ignore[return, assignment]
        """Migrate data in batches.

        Args:
            batch_size: Number of requests to migrate per batch
            source: Source backend ('file' or 'redis')
            destination: Destination backend ('file' or 'redis')

        Returns:
            Dictionary with migration status and details
        """
        migration_details: dict[str, Any] = {
            'batch_size': batch_size,
            'source': source,
            'destination': destination,
            'timestamp': time.time(),
            'total_batches': 0,
            'migrated_count': 0,
            'failed_count': 0,
            'success': False,
        }

        try:
            if source == 'file' and destination == 'redis':
                if not self._redis_store:
                    migration_details['error'] = 'Redis store not available'
                    return migration_details

                parent_run_ids = self._file_store.list_parent_run_ids()
                batch_num = 0
                total_migrated = 0
                total_failed = 0

                for parent_run_id in parent_run_ids:
                    try:
                        snapshot = self._file_store.load(parent_run_id)
                        request_ids = list(snapshot.requests.keys())

                        # Process in batches
                        for i in range(0, len(request_ids), batch_size):
                            batch = request_ids[i : i + batch_size]
                            batch_num += 1

                            for request_id in batch:
                                try:
                                    request_dict = snapshot.requests[request_id]
                                    request = request_from_dict(request_dict)
                                    self._redis_store.save_request(
                                        parent_run_id, request
                                    )
                                    total_migrated += 1
                                except Exception as e:
                                    logger.error(
                                        f'Batch migration failed for request {request_id}: {e}'
                                    )
                                    total_failed += 1

                    except Exception as e:
                        logger.error(
                            f'Batch migration failed for parent run {parent_run_id}: {e}'
                        )

                migration_details['total_batches'] = batch_num
                migration_details['migrated_count'] = total_migrated
                migration_details['failed_count'] = total_failed
                migration_details['success'] = True

            elif source == 'redis' and destination == 'file':
                if not self._redis_store:
                    migration_details['error'] = 'Redis store not available'
                    return migration_details

                parent_run_ids = self._redis_store.list_parent_run_ids()
                batch_num = 0
                total_migrated = 0
                total_failed = 0

                for parent_run_id in parent_run_ids:
                    try:
                        request_ids = list(
                            self._redis_store.get_all_request_ids(parent_run_id)
                        )

                        # Process in batches
                        for i in range(0, len(request_ids), batch_size):
                            batch = request_ids[i : i + batch_size]
                            batch_num += 1

                            # Load existing snapshot
                            snapshot = self._file_store.load(parent_run_id)
                            requests = dict(snapshot.requests)

                            for request_id in batch:
                                try:
                                    request = self._redis_store.get_request(
                                        parent_run_id, request_id
                                    )
                                    if request is not None:
                                        requests[request_id] = request.to_dict()  # type: ignore[assignment]
                                        total_migrated += 1
                                except Exception as e:
                                    logger.error(
                                        f'Batch migration failed for request {request_id}: {e}'
                                    )
                                    total_failed += 1

                            # Convert to SubagentApprovalRequest objects
                            request_objects: dict[str, SubagentApprovalRequest] = {}
                            for rid, rdict in requests.items():
                                with contextlib.suppress(Exception):
                                    request_objects[rid] = request_from_dict(rdict)

                            self._file_store.save(parent_run_id, request_objects, {})

                    except Exception as e:
                        logger.error(
                            f'Batch migration failed for parent run {parent_run_id}: {e}'
                        )

                migration_details['total_batches'] = batch_num
                migration_details['migrated_count'] = total_migrated
                migration_details['failed_count'] = total_failed
                migration_details['success'] = True

            else:
                migration_details['error'] = (
                    f'Invalid migration path: {source} -> {destination}'
                )

        except Exception as e:
            logger.error(f'Incremental migration failed: {e}')
            migration_details['error'] = str(e)
            migration_details['success'] = False

        return migration_details

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics for this store."""
        self._metrics.update_circuit_breaker_stats(self.get_circuit_breaker_stats())
        self._metrics.update_redis_availability(self._redis_available)
        return self._metrics.get_all_metrics()

    def _calculate_dynamic_sync_interval(self) -> int:
        """Calculate dynamic sync interval based on load."""
        if not self.config.enable_dynamic_sync:
            return self.config.sync_interval_seconds

        # Get operation metrics to determine load
        save_metrics = self._metrics.get_operation_metrics(OperationType.SAVE_REQUEST)
        update_metrics = self._metrics.get_operation_metrics(
            OperationType.UPDATE_REQUEST_STATUS
        )

        # Calculate operations per second
        total_ops = save_metrics.count + update_metrics.count
        if total_ops == 0:
            return self.config.sync_interval_seconds

        # Calculate rate based on avg latency
        avg_latency = (save_metrics.avg_latency_ms + update_metrics.avg_latency_ms) / 2

        # Higher load (more operations, lower latency) -> shorter sync interval
        # Lower load (fewer operations, higher latency) -> longer sync interval
        if avg_latency < 10:  # Very fast operations
            load_factor = 2.0
        elif avg_latency < 50:  # Fast operations
            load_factor = 1.5
        elif avg_latency < 100:  # Normal operations
            load_factor = 1.0
        elif avg_latency < 500:  # Slow operations
            load_factor = 0.5
        else:  # Very slow operations
            load_factor = 0.25

        # Calculate new interval
        new_interval = int(self.config.sync_interval_seconds / load_factor)

        # Clamp to min/max bounds
        new_interval = max(
            self.config.min_sync_interval_seconds,
            min(self.config.max_sync_interval_seconds, new_interval),
        )

        # Log if interval changed significantly
        if abs(new_interval - self._current_sync_interval) > 10:
            logger.info(
                f'Dynamic sync interval adjusted: {self._current_sync_interval}s -> {new_interval}s '
                f'(avg_latency: {avg_latency:.2f}ms, load_factor: {load_factor:.2f})'
            )

        self._current_sync_interval = new_interval
        return new_interval

    def should_sync(self) -> bool:
        """Check if sync should be performed based on dynamic interval."""
        if self._last_sync_time is None:
            return True

        import time

        elapsed = time.time() - self._last_sync_time
        sync_interval = self._calculate_dynamic_sync_interval()
        return elapsed >= sync_interval

    def record_sync(self) -> None:
        """Record that a sync was performed."""
        import time

        self._last_sync_time = time.time()

    def cleanup_orphaned_requests(
        self,
        max_age_seconds: float = 3600,
        timeout_seconds: float = 180,
    ) -> dict:
        """Clean up orphaned requests.

        Args:
            max_age_seconds: Maximum age for resolved requests before cleanup
            timeout_seconds: Timeout for pending requests before marking as timed out

        Returns:
            Cleanup report with counts of cleaned items
        """
        import time

        now = time.time()
        cleanup_report = {
            'timed_out_requests': 0,
            'expired_resolved_requests': 0,
            'orphaned_parent_runs': 0,
            'errors': 0,
        }

        try:
            # Get all parent run IDs
            parent_run_ids = self.list_parent_run_ids()

            for parent_run_id in parent_run_ids:
                try:
                    # Load snapshot
                    snapshot = self._file_store.load(parent_run_id)

                    # Check for orphaned parent run (no active references)
                    # This is a simple heuristic - in production, you might want to check
                    # against an active runs registry
                    pending_count = sum(
                        1
                        for r in snapshot.requests.values()
                        if r.get('status') == 'pending'
                    )

                    # If no pending requests and old, consider for cleanup
                    if pending_count == 0:
                        # Check age of the queue file
                        queue_path = self._file_store.queue_path(parent_run_id)
                        if (
                            queue_path.exists()
                            and (now - queue_path.stat().st_mtime) > max_age_seconds
                            and self.delete_parent_run(parent_run_id)
                        ):
                            cleanup_report['expired_resolved_requests'] += len(
                                snapshot.requests
                            )
                            cleanup_report['orphaned_parent_runs'] += 1
                        continue

                    # Check for timed out pending requests
                    for request_id, request_data in snapshot.requests.items():
                        if request_data.get('status') == 'pending':
                            created_at = request_data.get('created_at', '')
                            if created_at:
                                try:
                                    from datetime import datetime

                                    created_time = datetime.fromisoformat(created_at)
                                    age_seconds = now - created_time.timestamp()

                                    if age_seconds > timeout_seconds:
                                        # Mark as timed out
                                        self.update_request_status(
                                            parent_run_id,
                                            request_id,
                                            ApprovalRequestStatus.TIMEOUT,
                                            reason=f'Request timed out after {age_seconds:.0f}s',
                                        )
                                        cleanup_report['timed_out_requests'] += 1
                                except Exception as e:
                                    logger.error(
                                        f'Error parsing created_at for request {request_id}: {e}'
                                    )
                                    cleanup_report['errors'] += 1

                except Exception as e:
                    logger.error(f'Error cleaning up parent run {parent_run_id}: {e}')
                    cleanup_report['errors'] += 1

            logger.info(f'Cleanup completed: {cleanup_report}')
            return cleanup_report

        except Exception as e:
            logger.error(f'Cleanup failed: {e}')
            cleanup_report['errors'] += 1
            return cleanup_report

    def save_request(
        self,
        parent_run_id: str,
        request: SubagentApprovalRequest,
    ) -> None:
        """Save a request with dual-write strategy."""
        start_time = time.time()

        with MetricsContext(self._metrics, OperationType.SAVE_REQUEST):
            errors = []

            # Validate request
            is_valid, validation_errors = self.validate_request(request)
            if not is_valid:
                raise ValueError(f'Invalid request: {validation_errors}')

            # Check rate limit
            if not self._check_rate_limit(request.subagent_id):
                raise Exception(
                    f'Rate limit exceeded for subagent {request.subagent_id}'
                )

            # Check for duplicate
            if self._is_duplicate_request(request):
                logger.info(f'Skipping duplicate request: {request.request_id}')
                return

            # Add audit entry
            self._add_audit_entry(
                'save_request',
                parent_run_id,
                request.request_id,
                correlation_id=self.config.correlation_id or request.request_id,
            )

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Write to Redis first (primary)
                try:
                    self._call_redis(
                        self._redis_store.save_request, parent_run_id, request
                    )
                except Exception as e:
                    errors.append(f'Redis write failed: {e}')
                    logger.error(
                        f'Redis write failed for request {request.request_id}: {e}'
                    )
                    self._redis_available = False

            # Write to file (backup or primary)
            try:
                # Load existing snapshot, add request, save back
                snapshot = self._file_store.load(parent_run_id)
                request_dict = request.to_dict()

                # Add TTL metadata if enabled
                if self.config.enable_ttl:
                    request_dict['ttl'] = self.config.default_ttl_seconds
                    request_dict['expires_at'] = (
                        time.time() + self.config.default_ttl_seconds
                    )

                # Compress if enabled
                if self.config.enable_compression:
                    request_json = json.dumps(request_dict)
                    compressed_data, is_compressed = self._compress_data(request_json)
                    if is_compressed:
                        request_dict['_compressed'] = True
                        request_dict['_data'] = compressed_data
                    else:
                        request_dict['_compressed'] = False

                # Encrypt if enabled
                if self.config.enable_encryption:
                    request_json = json.dumps(request_dict)
                    encrypted_data, is_encrypted = self._encrypt_data(request_json)
                    if is_encrypted:
                        request_dict['_encrypted'] = True
                        request_dict['_data'] = encrypted_data
                    else:
                        request_dict['_encrypted'] = False

                snapshot.requests[request.request_id] = request_dict
                # Use internal save method with snapshot
                with self._file_store.lock(parent_run_id):
                    self._file_store._save_unlocked(parent_run_id, snapshot)
            except Exception as e:
                errors.append(f'File write failed: {e}')
                logger.error(f'File write failed for request {request.request_id}: {e}')

            if (
                not self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Write to Redis (backup)
                try:
                    self._call_redis(
                        self._redis_store.save_request, parent_run_id, request
                    )
                except Exception as e:
                    errors.append(f'Redis write failed: {e}')
                    logger.error(
                        f'Redis write failed for request {request.request_id}: {e}'
                    )
                    self._redis_available = False

            if errors and len(errors) >= 2:
                raise Exception(
                    f'All writes failed for request {request.request_id}: {errors}'
                )

            # Create notification for successful save
            self._create_notification(
                'request_submitted',
                f'Request {request.request_id} submitted for approval',
                request_id=request.request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            # Apply approval policies
            self.apply_approval_policies(parent_run_id, request)

            # Record performance metrics
            elapsed_time = time.time() - start_time
            self.record_performance_metric(
                request.request_id, 'save_time_seconds', elapsed_time
            )

    def get_request(
        self,
        parent_run_id: str,
        request_id: str,
    ) -> Optional[SubagentApprovalRequest]:
        """Get a request from file (primary) with Redis fallback."""
        with MetricsContext(self._metrics, OperationType.GET_REQUEST):
            # Try file first (faster)
            try:
                snapshot = self._file_store.load(parent_run_id)
                raw = snapshot.requests.get(request_id)
                if raw:
                    # Handle decryption
                    if raw.get('_encrypted'):
                        encrypted_data = raw.get('_data', '')
                        decrypted = self._decrypt_data(encrypted_data, True)
                        raw = json.loads(decrypted)
                        # Remove encryption metadata
                        raw.pop('_encrypted', None)
                        raw.pop('_data', None)

                    # Handle decompression
                    if raw.get('_compressed'):
                        compressed_data = raw.get('_data', '')
                        decompressed = self._decompress_data(compressed_data, True)
                        raw = json.loads(decompressed)
                        # Remove compression metadata
                        raw.pop('_compressed', None)
                        raw.pop('_data', None)

                    # Check TTL expiration
                    if (
                        self.config.enable_ttl
                        and raw.get('expires_at')
                        and time.time() > raw['expires_at']
                    ):
                        logger.info(f'Request {request_id} has expired (TTL)')
                        return None

                    from teaagent.subagents._approval_queue_store import (
                        request_from_dict,
                    )

                    return request_from_dict(raw)
            except Exception as e:
                logger.error(f'File read failed for request {request_id}: {e}')

            # Fallback to Redis
            if self._redis_available and self._redis_store:
                try:
                    return self._call_redis(
                        self._redis_store.get_request, parent_run_id, request_id
                    )
                except Exception as e:
                    logger.error(f'Redis read failed for request {request_id}: {e}')

            return None

    def update_request_status(
        self,
        parent_run_id: str,
        request_id: str,
        status: ApprovalRequestStatus,
        *,
        reason: Optional[str] = None,
        approved_by: str = 'human',
    ) -> bool:
        """Update request status with dual-write strategy."""
        with MetricsContext(self._metrics, OperationType.UPDATE_REQUEST_STATUS):
            errors = []

            # Record approval history
            if self.config.enable_approval_history:
                self._ensure_approval_history()

                with self._lock:
                    if request_id not in self._approval_history:
                        self._approval_history[request_id] = []

                    self._approval_history[request_id].append(
                        {
                            'timestamp': time.time(),
                            'status': status.value,
                            'reason': reason,
                            'approved_by': approved_by,
                            'parent_run_id': parent_run_id,
                        }
                    )

            # Check dependencies before approval
            if (
                status == ApprovalRequestStatus.APPROVED
                and self.config.enable_dependencies
            ):
                dep_status = self.check_dependencies(request_id, parent_run_id)
                if dep_status.get('enabled') and not dep_status.get(
                    'all_satisfied', True
                ):
                    logger.warning(
                        f'Cannot approve request {request_id}: dependencies not satisfied'
                    )
                    raise Exception(
                        f'Cannot approve request {request_id}: dependencies not satisfied: {dep_status.get("unsatisfied_ids")}'
                    )

            # Check compliance before approval
            if (
                status == ApprovalRequestStatus.APPROVED
                and self.config.enable_compliance_checks
            ):
                request = self.get_request(parent_run_id, request_id)
                if request:
                    compliance_result = self.check_compliance(request)
                    if compliance_result.get('enabled') and not compliance_result.get(
                        'is_compliant', True
                    ):
                        logger.warning(
                            f'Cannot approve request {request_id}: compliance violations: {compliance_result.get("violations")}'
                        )
                        raise Exception(
                            f'Cannot approve request {request_id}: compliance violations: {compliance_result.get("violations")}'
                        )

            # Check quota for approvals (warning only, doesn't block)
            if (
                status == ApprovalRequestStatus.APPROVED
                and not self.check_approval_quota(approved_by)
            ):
                logger.warning(
                    f'User {approved_by} has exceeded approval quota (warning only)'
                )

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Update Redis first (primary)
                try:
                    self._call_redis(
                        self._redis_store.update_request_status,
                        parent_run_id,
                        request_id,
                        status,
                        reason=reason,
                        approved_by=approved_by,
                    )
                except Exception as e:
                    errors.append(f'Redis update failed: {e}')
                    logger.error(f'Redis update failed for request {request_id}: {e}')
                    self._redis_available = False

            # Update file (backup or primary)
            try:
                self._file_store.update_request_status(
                    parent_run_id,
                    request_id,
                    status,
                    reason=reason,
                    approved_by=approved_by,
                )
            except Exception as e:
                errors.append(f'File update failed: {e}')
                logger.error(f'File update failed for request {request_id}: {e}')

            if (
                not self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Update Redis (backup)
                try:
                    self._call_redis(
                        self._redis_store.update_request_status,
                        parent_run_id,
                        request_id,
                        status,
                        reason=reason,
                        approved_by=approved_by,
                    )
                except Exception as e:
                    errors.append(f'Redis update failed: {e}')
                    logger.error(f'Redis update failed for request {request_id}: {e}')
                    self._redis_available = False

            if errors and len(errors) >= 2:
                logger.error(f'All updates failed for request {request_id}: {errors}')
                return False

            return True

    def get_pending_requests(
        self,
        parent_run_id: str,
    ) -> list[SubagentApprovalRequest]:
        """Get pending requests from file (faster)."""
        with MetricsContext(self._metrics, OperationType.GET_PENDING_REQUESTS):
            try:
                snapshot = self._file_store.load(parent_run_id)
                from teaagent.subagents._approval_queue_store import (
                    pending_requests_from_snapshot,
                )

                return pending_requests_from_snapshot(snapshot)
            except Exception as e:
                logger.error(f'File read failed for pending requests: {e}')

            # Fallback to Redis
            if self._redis_available and self._redis_store:
                try:
                    return self._call_redis(
                        self._redis_store.get_pending_requests, parent_run_id
                    )
                except Exception as e:
                    logger.error(f'Redis read failed for pending requests: {e}')

            return []

    def save_batch(
        self,
        parent_run_id: str,
        batch: ApprovalBatch,
    ) -> None:
        """Save a batch with dual-write strategy."""
        with MetricsContext(self._metrics, OperationType.SAVE_BATCH):
            errors = []

            if (
                self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Save to Redis first (primary)
                try:
                    self._call_redis(self._redis_store.save_batch, parent_run_id, batch)
                except Exception as e:
                    errors.append(f'Redis write failed: {e}')
                    logger.error(f'Redis write failed for batch {batch.batch_id}: {e}')
                    self._redis_available = False

            # Save to file (backup or primary)
            try:
                # Load existing snapshot, add batch, save back
                snapshot = self._file_store.load(parent_run_id)
                snapshot.batches[batch.batch_id] = batch.to_dict()
                with self._file_store.lock(parent_run_id):
                    self._file_store._save_unlocked(parent_run_id, snapshot)
            except Exception as e:
                errors.append(f'File write failed: {e}')
                logger.error(f'File write failed for batch {batch.batch_id}: {e}')

            if (
                not self.config.redis_primary
                and self._redis_available
                and self._redis_store
            ):
                # Save to Redis (backup)
                try:
                    self._call_redis(self._redis_store.save_batch, parent_run_id, batch)
                except Exception as e:
                    errors.append(f'Redis write failed: {e}')
                    logger.error(f'Redis write failed for batch {batch.batch_id}: {e}')
                    self._redis_available = False

            if errors and len(errors) >= 2:
                raise Exception(
                    f'All writes failed for batch {batch.batch_id}: {errors}'
                )

    def get_batch(
        self,
        parent_run_id: str,
        batch_id: str,
    ) -> Optional[ApprovalBatch]:
        """Get a batch from file with Redis fallback."""
        with MetricsContext(self._metrics, OperationType.GET_BATCH):
            # Try file first
            try:
                snapshot = self._file_store.load(parent_run_id)
                raw = snapshot.batches.get(batch_id)
                if raw:
                    # ApprovalBatch doesn't have from_dict, reconstruct manually
                    batch = ApprovalBatch(
                        batch_id=raw.get('batch_id', batch_id),
                        parent_run_id=raw.get('parent_run_id', parent_run_id),
                        created_at=raw.get('created_at', ''),
                        status=ApprovalRequestStatus(raw.get('status', 'pending')),
                    )
                    return batch
            except Exception as e:
                logger.error(f'File read failed for batch {batch_id}: {e}')

            # Fallback to Redis
            if self._redis_available and self._redis_store:
                try:
                    return self._call_redis(
                        self._redis_store.get_batch, parent_run_id, batch_id
                    )
                except Exception as e:
                    logger.error(f'Redis read failed for batch {batch_id}: {e}')

            return None

    def sync_to_file(self, parent_run_id: str) -> dict:
        """Sync Redis state to file."""
        start_time = time.perf_counter()
        with MetricsContext(self._metrics, OperationType.SYNC_TO_FILE):
            if not self._redis_available or not self._redis_store:
                return {'synced': 0, 'errors': 0, 'error': 'Redis not available'}

            try:
                # Get all requests from Redis
                request_ids = self._call_redis(
                    self._redis_store.get_all_request_ids, parent_run_id
                )
                batch_ids = self._call_redis(
                    self._redis_store.get_all_batch_ids, parent_run_id
                )

                synced = 0
                errors = 0

                # Sync requests
                for request_id in request_ids:
                    try:
                        request = self._call_redis(
                            self._redis_store.get_request, parent_run_id, request_id
                        )
                        if request:
                            # Load existing snapshot, add request, save back
                            snapshot = self._file_store.load(parent_run_id)
                            snapshot.requests[request_id] = request.to_dict()
                            with self._file_store.lock(parent_run_id):
                                self._file_store._save_unlocked(parent_run_id, snapshot)
                            synced += 1
                    except Exception as e:
                        logger.error(f'Sync failed for request {request_id}: {e}')
                        errors += 1

                # Sync batches
                for batch_id in batch_ids:
                    try:
                        batch = self._call_redis(
                            self._redis_store.get_batch, parent_run_id, batch_id
                        )
                        if batch:
                            # Load existing snapshot, add batch, save back
                            snapshot = self._file_store.load(parent_run_id)
                            snapshot.batches[batch_id] = batch.to_dict()
                            with self._file_store.lock(parent_run_id):
                                self._file_store._save_unlocked(parent_run_id, snapshot)
                            synced += 1
                    except Exception as e:
                        logger.error(f'Sync failed for batch {batch_id}: {e}')
                        errors += 1

                # Adjust sync interval based on operation latency
                operation_latency = time.perf_counter() - start_time
                self._adjust_sync_interval(operation_latency)

                return {'synced': synced, 'errors': errors}
            except Exception as e:
                logger.error(f'Sync to file failed: {e}')
                return {'synced': 0, 'errors': 0, 'error': str(e)}

    def sync_to_redis(self, parent_run_id: str) -> dict:
        """Sync file state to Redis."""
        start_time = time.perf_counter()
        with MetricsContext(self._metrics, OperationType.SYNC_TO_REDIS):
            if not self._redis_available or not self._redis_store:
                return {'synced': 0, 'errors': 0, 'error': 'Redis not available'}

            try:
                snapshot = self._file_store.load(parent_run_id)

                synced = 0
                errors = 0

                # Sync requests
                for request_id, raw in snapshot.requests.items():
                    try:
                        from teaagent.subagents._approval_queue_store import (
                            request_from_dict,
                        )

                        request = request_from_dict(raw)
                        self._call_redis(
                            self._redis_store.save_request, parent_run_id, request
                        )
                        synced += 1
                    except Exception as e:
                        logger.error(f'Sync failed for request {request_id}: {e}')
                        errors += 1

                # Sync batches
                for batch_id, raw in snapshot.batches.items():
                    try:
                        batch = ApprovalBatch(
                            batch_id=raw.get('batch_id', batch_id),
                            parent_run_id=raw.get('parent_run_id', parent_run_id),
                            created_at=raw.get('created_at', ''),
                            status=ApprovalRequestStatus(raw.get('status', 'pending')),
                        )
                        self._call_redis(
                            self._redis_store.save_batch, parent_run_id, batch
                        )
                        synced += 1
                    except Exception as e:
                        logger.error(f'Sync failed for batch {batch_id}: {e}')
                        errors += 1

                # Adjust sync interval based on operation latency
                operation_latency = time.perf_counter() - start_time
                self._adjust_sync_interval(operation_latency)

                return {'synced': synced, 'errors': errors}
            except Exception as e:
                logger.error(f'Sync to Redis failed: {e}')
                return {'synced': 0, 'errors': 0, 'error': str(e)}

    def validate_consistency(self, parent_run_id: str) -> dict:
        """Validate consistency between file and Redis backends."""
        with MetricsContext(self._metrics, OperationType.VALIDATE_CONSISTENCY):
            try:
                # Get request counts
                file_snapshot = self._file_store.load(parent_run_id)
                file_request_ids = set(file_snapshot.requests.keys())
                file_batch_ids = set(file_snapshot.batches.keys())

                redis_request_ids = set()
                redis_batch_ids = set()

                if self._redis_available and self._redis_store:
                    redis_request_ids = self._call_redis(
                        self._redis_store.get_all_request_ids, parent_run_id
                    )
                    redis_batch_ids = self._call_redis(
                        self._redis_store.get_all_batch_ids, parent_run_id
                    )

                # If Redis is not available, consider it consistent (no discrepancy to measure)
                if not self._redis_available or not self._redis_store:
                    return {
                        'file_requests': len(file_request_ids),
                        'redis_requests': 0,
                        'file_batches': len(file_batch_ids),
                        'redis_batches': 0,
                        'missing_in_redis': 0,
                        'missing_in_file': 0,
                        'consistency_rate': 1.0,
                        'redis_available': False,
                    }

                # Calculate consistency
                missing_in_redis = file_request_ids - redis_request_ids
                missing_in_file = redis_request_ids - file_request_ids

                total = max(len(file_request_ids), len(redis_request_ids))
                consistency_rate = 1.0
                if total > 0:
                    consistency_rate = (
                        1.0 - (len(missing_in_redis) + len(missing_in_file)) / total
                    )
                else:
                    # Both empty, consider consistent
                    consistency_rate = 1.0

                return {
                    'file_requests': len(file_request_ids),
                    'redis_requests': len(redis_request_ids),
                    'file_batches': len(file_batch_ids),
                    'redis_batches': len(redis_batch_ids),
                    'missing_in_redis': len(missing_in_redis),
                    'missing_in_file': len(missing_in_file),
                    'consistency_rate': consistency_rate,
                    'redis_available': True,
                }
            except Exception as e:
                logger.error(f'Consistency validation failed: {e}')
                return {
                    'error': str(e),
                    'consistency_rate': 0.0,
                    'redis_available': self._redis_available,
                }

    def list_parent_run_ids(self) -> list[str]:
        """List parent run IDs from file (primary) with Redis fallback."""
        try:
            return self._file_store.list_parent_run_ids()
        except Exception as e:
            logger.error(f'File list failed: {e}')

        if self._redis_available and self._redis_store:
            try:
                return self._call_redis(self._redis_store.list_parent_run_ids)
            except Exception as e:
                logger.error(f'Redis list failed: {e}')

        return []

    def exists(self, parent_run_id: str) -> bool:
        """Check if parent run exists in file with Redis fallback."""
        try:
            return self._file_store.exists(parent_run_id)
        except Exception as e:
            logger.error(f'File exists check failed: {e}')

        if self._redis_available and self._redis_store:
            try:
                return self._call_redis(self._redis_store.exists, parent_run_id)
            except Exception as e:
                logger.error(f'Redis exists check failed: {e}')

        return False

    def delete_parent_run(self, parent_run_id: str) -> bool:
        """Delete parent run from both backends."""
        with MetricsContext(self._metrics, OperationType.DELETE_PARENT_RUN):
            errors = []

            # Delete from file
            try:
                path = self._file_store.queue_path(parent_run_id)
                if path.exists():
                    path.unlink(missing_ok=True)
            except Exception as e:
                errors.append(f'File delete failed: {e}')
                logger.error(f'File delete failed for {parent_run_id}: {e}')

            # Delete from Redis
            if self._redis_available and self._redis_store:
                try:
                    self._call_redis(self._redis_store.delete_parent_run, parent_run_id)
                except Exception as e:
                    errors.append(f'Redis delete failed: {e}')
                    logger.error(f'Redis delete failed for {parent_run_id}: {e}')

            if errors:
                logger.error(f'Delete errors for {parent_run_id}: {errors}')
                return False

            return True

    def _compress_data(self, data: str) -> tuple[str, bool]:
        """Compress data if enabled and above threshold."""
        if not self.config.enable_compression:
            return data, False

        data_bytes = data.encode('utf-8')
        if len(data_bytes) < self.config.compression_threshold_bytes:
            return data, False

        try:
            compressed = zlib.compress(data_bytes)
            # Only use compressed if it's actually smaller
            if len(compressed) < len(data_bytes):
                return compressed.decode('latin-1'), True
        except Exception as e:
            logger.warning(f'Compression failed: {e}')

        return data, False

    def _decompress_data(self, data: str, is_compressed: bool) -> str:
        """Decompress data if it was compressed."""
        if not is_compressed:
            return data

        try:
            compressed_bytes = data.encode('latin-1')
            decompressed = zlib.decompress(compressed_bytes)
            return decompressed.decode('utf-8')
        except Exception as e:
            logger.warning(f'Decompression failed: {e}')
            return data

    def _encrypt_data(self, data: str) -> tuple[str, bool]:
        """Encrypt data if encryption is enabled."""
        if not self.config.enable_encryption or self._cipher is None:
            return data, False

        try:
            data_bytes = data.encode('utf-8')
            encrypted = self._cipher.encrypt(data_bytes)
            return encrypted.decode('latin-1'), True
        except Exception as e:
            logger.warning(f'Encryption failed: {e}')
            return data, False

    def _decrypt_data(self, data: str, is_encrypted: bool) -> str:
        """Decrypt data if it was encrypted."""
        if not is_encrypted or self._cipher is None:
            return data

        try:
            encrypted_bytes = data.encode('latin-1')
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.warning(f'Decryption failed: {e}')
            return data

    def _compute_request_hash(self, request: SubagentApprovalRequest) -> str:
        """Compute hash for request deduplication."""
        hash_input = (
            f'{request.subagent_id}:{request.tool_name}:'
            f'{json.dumps(request.tool_arguments, sort_keys=True)}:'
            f'{request.permission_mode}:{request.isolation}'
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _is_duplicate_request(self, request: SubagentApprovalRequest) -> bool:
        """Check if request is a duplicate within deduplication window."""
        if not self.config.enable_deduplication:
            return False

        request_hash = self._compute_request_hash(request)
        current_time = time.time()

        # Clean up old hashes
        self._request_hashes = {
            h: t
            for h, t in self._request_hashes.items()
            if current_time - t < self.config.deduplication_window_seconds
        }

        # Check for duplicate
        if request_hash in self._request_hashes:
            logger.info(f'Duplicate request detected: {request.request_id}')
            return True

        # Store new hash
        self._request_hashes[request_hash] = current_time
        return False

    def health_check(self) -> dict[str, Any]:
        """Perform health check on the hybrid queue."""
        health: dict[str, Any] = {
            'status': 'healthy',
            'timestamp': time.time(),
            'components': {},
        }

        # Check file backend
        try:
            file_health = (
                self._file_store.health_check()
                if hasattr(self._file_store, 'health_check')
                else {'status': 'ok'}
            )
            health['components']['file'] = file_health
        except Exception as e:
            health['components']['file'] = {'status': 'error', 'error': str(e)}
            health['status'] = 'degraded'

        # Check Redis backend
        if self._redis_store:
            try:
                redis_available = self._check_redis_available()
                health['components']['redis'] = {
                    'status': 'ok' if redis_available else 'unavailable',
                    'available': redis_available,
                }
                if not redis_available:
                    health['status'] = 'degraded'
            except Exception as e:
                health['components']['redis'] = {'status': 'error', 'error': str(e)}
                health['status'] = 'degraded'

        # Check circuit breaker
        if self._circuit_breaker:
            stats = self.get_circuit_breaker_stats()
            health['components']['circuit_breaker'] = stats
            if stats and stats['state'] == 'open':
                health['status'] = 'degraded'

        # Check metrics
        try:
            metrics = self.get_metrics()
            health['components']['metrics'] = {
                'uptime_seconds': metrics.get('uptime_seconds', 0),
                'sync_errors': metrics.get('sync_errors', 0),
            }
        except Exception as e:
            health['components']['metrics'] = {'status': 'error', 'error': str(e)}

        return health

    def set_request_priority(
        self, parent_run_id: str, request_id: str, priority: int
    ) -> bool:
        """Set priority for a request (if priority queue enabled)."""
        if not self.config.enable_priority:
            logger.warning('Priority queue not enabled')
            return False

        try:
            # Load snapshot
            snapshot = self._file_store.load(parent_run_id)
            if request_id not in snapshot.requests:
                logger.warning(f'Request {request_id} not found')
                return False

            # Add priority metadata
            requests_dict = cast(dict[str, Any], snapshot.requests)
            requests_dict[request_id]['priority'] = priority
            requests_dict[request_id]['priority_set_at'] = time.time()

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            logger.info(f'Set priority {priority} for request {request_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to set priority: {e}')
            return False

    def get_pending_requests_by_priority(
        self, parent_run_id: str
    ) -> list[SubagentApprovalRequest]:
        """Get pending requests sorted by priority (if enabled)."""
        if not self.config.enable_priority:
            # Return regular pending requests
            return self.get_pending_requests(parent_run_id)

        try:
            snapshot = self._file_store.load(parent_run_id)
            pending = [
                r for r in snapshot.requests.values() if r.get('status') == 'pending'
            ]

            # Sort by priority (higher priority first)
            pending.sort(key=lambda r: r.get('priority', 0), reverse=True)

            from teaagent.subagents._approval_queue_store import (
                request_from_dict,
            )

            return [request_from_dict(r) for r in pending]
        except Exception as e:
            logger.error(f'Failed to get pending requests by priority: {e}')
            return []

    def validate_request(
        self, request: SubagentApprovalRequest
    ) -> tuple[bool, list[str]]:
        """Validate request against schema."""
        errors = []

        # Required fields
        if not request.request_id:
            errors.append('request_id is required')
        if not request.subagent_id:
            errors.append('subagent_id is required')
        if not request.tool_name:
            errors.append('tool_name is required')
        if not request.permission_mode:
            errors.append('permission_mode is required')

        # Validate tool_arguments is a dict
        if not isinstance(request.tool_arguments, dict):
            errors.append('tool_arguments must be a dictionary')

        # Validate isolation
        valid_isolations = ['shared', 'sandbox', 'isolated']
        if request.isolation not in valid_isolations:
            errors.append(f'isolation must be one of {valid_isolations}')

        # Validate permission_mode
        valid_modes = [
            'workspace-read',
            'workspace-write',
            'network',
            'system',
        ]
        if request.permission_mode not in valid_modes:
            errors.append(f'permission_mode must be one of {valid_modes}')

        # Validate timeout_seconds
        if request.timeout_seconds and request.timeout_seconds < 0:
            errors.append('timeout_seconds must be non-negative')

        return len(errors) == 0, errors

    def _check_rate_limit(self, subagent_id: str) -> bool:
        """Check if subagent is within rate limits."""
        if not self.config.enable_rate_limiting:
            return True

        current_time = time.time()
        minute_ago = current_time - 60

        # Clean up old timestamps
        self._rate_limit_tracker[subagent_id] = [
            ts for ts in self._rate_limit_tracker[subagent_id] if ts > minute_ago
        ]

        # Check rate limit
        request_count = len(self._rate_limit_tracker[subagent_id])
        if request_count >= self.config.rate_limit_requests_per_minute:
            logger.warning(
                f'Rate limit exceeded for subagent {subagent_id}: {request_count} requests/min'
            )
            self._record_security_event(
                'rate_limit_exceeded',
                'medium',
                {'subagent_id': subagent_id, 'request_count': request_count},
            )
            return False

        # Record this request
        self._rate_limit_tracker[subagent_id].append(current_time)
        return True

    def _add_audit_entry(
        self,
        action: str,
        parent_run_id: str,
        request_id: str,
        details: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Add entry to audit trail."""
        if not self.config.enable_audit_trail:
            return

        entry = {
            'timestamp': time.time(),
            'action': action,
            'parent_run_id': parent_run_id,
            'request_id': request_id,
            'correlation_id': correlation_id or self._generate_correlation_id(),
            'details': details or {},
        }
        self._audit_trail.append(entry)

        # Keep audit trail size manageable
        if len(self._audit_trail) > 10000:
            self._audit_trail = self._audit_trail[-5000:]

    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID for audit trail."""
        import uuid

        return str(uuid.uuid4())

    def _record_security_event(
        self,
        event_type: str,
        severity: str,
        details: dict[str, Any],
    ) -> None:
        """Record a security event."""
        if not self.config.enable_security_monitoring:
            return

        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'correlation_id': self.config.correlation_id,
        }
        self._security_events.append(event)

        # Keep security events manageable
        if len(self._security_events) > 1000:
            self._security_events = self._security_events[-500:]

        # Check for alert conditions
        self._check_security_alerts(event_type, severity)

    def _check_security_alerts(self, event_type: str, severity: str) -> None:
        """Check if security event should trigger an alert."""
        if severity in ('critical', 'high'):
            alert = {
                'timestamp': time.time(),
                'event_type': event_type,
                'severity': severity,
                'details': f'High severity security event: {event_type}',
            }
            self._security_alerts.append(alert)

            # Keep alerts manageable
            if len(self._security_alerts) > 100:
                self._security_alerts = self._security_alerts[-50:]

            logger.warning(f'Security alert triggered: {event_type} ({severity})')

        # Check for repeated events of the same type
        recent_events = [
            e
            for e in self._security_events[-100:]
            if e['event_type'] == event_type and time.time() - e['timestamp'] < 300
        ]
        if len(recent_events) >= self.config.security_alert_threshold:
            alert = {
                'timestamp': time.time(),
                'event_type': 'repeated_security_events',
                'severity': 'high',
                'details': f'Repeated security events: {event_type} ({len(recent_events)} in 5 minutes)',
            }
            self._security_alerts.append(alert)
            logger.warning(f'Repeated security events detected: {event_type}')

    def get_security_status(self) -> dict[str, Any]:
        """Get security status and recent events."""
        return {
            'timestamp': time.time(),
            'monitoring_enabled': self.config.enable_security_monitoring,
            'total_security_events': len(self._security_events),
            'total_alerts': len(self._security_alerts),
            'recent_events': self._security_events[-10:],
            'recent_alerts': self._security_alerts[-5:],
            'alert_threshold': self.config.security_alert_threshold,
        }

    def comprehensive_health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check of the hybrid queue.

        Returns:
            Dictionary with health status details
        """
        health_status: dict[str, Any] = {
            'timestamp': time.time(),
            'overall_status': 'healthy',
            'components': {},
            'issues': [],
        }

        # Check file store
        file_status = self._check_file_store_health()
        health_status['components']['file_store'] = file_status
        if file_status['status'] != 'healthy':
            health_status['overall_status'] = 'degraded'
            health_status['issues'].append(
                f'File store: {file_status.get("error", "unhealthy")}'
            )

        # Check Redis store if available
        if self._redis_store:
            redis_status = self._check_redis_store_health()
            health_status['components']['redis_store'] = redis_status
            if redis_status['status'] != 'healthy':
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(
                    f'Redis store: {redis_status.get("error", "unhealthy")}'
                )

        # Check consistency
        if self._redis_store:
            consistency = self.validate_global_consistency()
            health_status['components']['consistency'] = consistency
            if consistency['consistency_rate'] < 0.99:
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(
                    f'Consistency rate: {consistency["consistency_rate"]:.2%}'
                )

        # Check security status
        if self.config.enable_security_monitoring:
            security_status = self.get_security_status()
            health_status['components']['security'] = security_status
            if security_status['total_alerts'] > 0:
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(
                    f'Security alerts: {security_status["total_alerts"]}'
                )

        # Check circuit breaker
        if self._circuit_breaker:
            circuit_stats = self.get_circuit_breaker_stats()
            health_status['components']['circuit_breaker'] = circuit_stats
            if circuit_stats and circuit_stats.get('state') != 'closed':
                health_status['overall_status'] = 'degraded'
                health_status['issues'].append(
                    f'Circuit breaker: {circuit_stats.get("state")}'
                )

        return health_status

    def _check_file_store_health(self) -> dict[str, Any]:
        """Check file store health."""
        status = {
            'status': 'healthy',
            'error': None,
            'details': {},
        }

        try:
            # Test write operation
            test_parent_run_id = 'health-check-file'
            test_request = SubagentApprovalRequest(
                request_id='health-check-request',
                subagent_id='health-check',
                parent_run_id=test_parent_run_id,
                subagent_name='health-check',
                tool_name='health_check',
                tool_arguments={'test': 'data'},
                permission_mode='read',
                isolation='none',
            )
            self._file_store.save(
                test_parent_run_id, {test_request.request_id: test_request}, {}
            )

            # Test read operation
            snapshot = self._file_store.load(test_parent_run_id)
            status['details']['read_success'] = (
                snapshot.parent_run_id == test_parent_run_id
            )

            # Cleanup
            self._file_store.delete(test_parent_run_id)
            status['details']['cleanup_success'] = True

        except Exception as e:
            status['status'] = 'unhealthy'
            status['error'] = str(e)

        return status

    def _check_redis_store_health(self) -> dict[str, Any]:
        """Check Redis store health."""
        status = {
            'status': 'healthy',
            'error': None,
            'details': {},
        }

        try:
            # Test connection
            self._redis_store.redis_client.ping()
            status['details']['ping_success'] = True

            # Test write operation
            test_parent_run_id = 'health-check-redis'
            test_request = SubagentApprovalRequest(
                request_id='health-check-request',
                subagent_id='health-check',
                parent_run_id=test_parent_run_id,
                subagent_name='health-check',
                tool_name='health_check',
                tool_arguments={'test': 'data'},
                permission_mode='read',
                isolation='none',
            )
            self._redis_store.save_request(test_parent_run_id, test_request)
            status['details']['write_success'] = True

            # Test read operation
            loaded = self._redis_store.get_request(
                test_parent_run_id, test_request.request_id
            )
            status['details']['read_success'] = loaded is not None

            # Cleanup
            self._redis_store.delete(test_parent_run_id)
            status['details']['cleanup_success'] = True

        except Exception as e:
            status['status'] = 'unhealthy'
            status['error'] = str(e)

        return status

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        # Update metrics with current state
        self._prometheus_exporter.set_metric(
            'hybrid_queue_redis_available',
            1.0 if self._redis_available else 0.0,
            'gauge',
            'Whether Redis backend is available',
        )

        self._prometheus_exporter.set_metric(
            'hybrid_queue_file_primary',
            1.0 if not self.config.redis_primary else 0.0,
            'gauge',
            'Whether file backend is primary',
        )

        self._prometheus_exporter.set_metric(
            'hybrid_queue_security_events_total',
            len(self._security_events),
            'counter',
            'Total security events',
        )

        self._prometheus_exporter.set_metric(
            'hybrid_queue_security_alerts_total',
            len(self._security_alerts),
            'counter',
            'Total security alerts',
        )

        self._prometheus_exporter.set_metric(
            'hybrid_queue_audit_trail_size',
            len(self._audit_trail),
            'gauge',
            'Size of audit trail',
        )

        # Add circuit breaker metrics
        if self._circuit_breaker:
            stats = self.get_circuit_breaker_stats()
            if stats:
                self._prometheus_exporter.set_metric(
                    'hybrid_queue_circuit_breaker_state',
                    1.0 if stats.get('state') == 'closed' else 0.0,
                    'gauge',
                    'Circuit breaker state (1=closed, 0=open)',
                )
                self._prometheus_exporter.set_metric(
                    'hybrid_queue_circuit_breaker_failures',
                    stats.get('failure_count', 0),
                    'counter',
                    'Circuit breaker failure count',
                )

        return self._prometheus_exporter.export_metrics()

    def _update_analytics(
        self,
        request: SubagentApprovalRequest,
        old_status: Optional[ApprovalRequestStatus] = None,
    ) -> None:
        """Update request analytics.

        Args:
            request: The request to track
            old_status: Previous status for state transitions
        """
        if not self.config.enable_analytics:
            return

        self._ensure_analytics()

        # Track by subagent
        subagent_id = request.subagent_id
        if subagent_id not in self._analytics['by_subagent']:
            self._analytics['by_subagent'][subagent_id] = {
                'total': 0,
                'approved': 0,
                'denied': 0,
                'cancelled': 0,
                'pending': 0,
            }
        self._analytics['by_subagent'][subagent_id]['total'] += 1

        # Track by tool
        tool_name = request.tool_name
        if tool_name not in self._analytics['by_tool']:
            self._analytics['by_tool'][tool_name] = {
                'total': 0,
                'approved': 0,
                'denied': 0,
                'cancelled': 0,
                'pending': 0,
            }
        self._analytics['by_tool'][tool_name]['total'] += 1

        # Update status counts
        if request.status == ApprovalRequestStatus.APPROVED:
            self._analytics['approved_requests'] += 1
            self._analytics['by_subagent'][subagent_id]['approved'] += 1
            self._analytics['by_tool'][tool_name]['approved'] += 1
        elif request.status == ApprovalRequestStatus.DENIED:
            self._analytics['denied_requests'] += 1
            self._analytics['by_subagent'][subagent_id]['denied'] += 1
            self._analytics['by_tool'][tool_name]['denied'] += 1
        elif request.status == ApprovalRequestStatus.CANCELLED:
            self._analytics['cancelled_requests'] += 1
            self._analytics['by_subagent'][subagent_id]['cancelled'] += 1
            self._analytics['by_tool'][tool_name]['cancelled'] += 1
        elif request.status == ApprovalRequestStatus.PENDING:
            self._analytics['pending_requests'] += 1
            self._analytics['by_subagent'][subagent_id]['pending'] += 1
            self._analytics['by_tool'][tool_name]['pending'] += 1

        self._analytics['total_requests'] += 1

        # Calculate approval rate
        total_decisions = (
            self._analytics['approved_requests'] + self._analytics['denied_requests']
        )
        if total_decisions > 0:
            self._analytics['approval_rate'] = (
                self._analytics['approved_requests'] / total_decisions
            )

    def get_analytics(self) -> dict[str, Any]:
        """Get request analytics.

        Returns:
            Dictionary with analytics data
        """
        return {
            'timestamp': time.time(),
            'total_requests': self._analytics['total_requests'],
            'approved_requests': self._analytics['approved_requests'],
            'denied_requests': self._analytics['denied_requests'],
            'cancelled_requests': self._analytics['cancelled_requests'],
            'pending_requests': self._analytics['pending_requests'],
            'approval_rate': self._analytics['approval_rate'],
            'average_approval_time_seconds': self._analytics[
                'average_approval_time_seconds'
            ],
            'by_subagent': self._analytics['by_subagent'],
            'by_tool': self._analytics['by_tool'],
        }

    def get_statistics_dashboard(self) -> dict[str, Any]:
        """Get comprehensive statistics dashboard.

        Returns:
            Dictionary with comprehensive statistics
        """
        dashboard: dict[str, Any] = {
            'timestamp': time.time(),
            'queue_health': 'unknown',
            'requests': {},
            'performance': {},
            'security': {},
            'backend_status': {},
        }

        # Queue health
        try:
            health = self.comprehensive_health_check()
            dashboard['queue_health'] = health['overall_status']
        except Exception as e:
            logger.error(f'Failed to get health status: {e}')

        # Request statistics
        try:
            parent_run_ids = self.list_parent_run_ids()
            total_requests = 0
            pending_requests = 0
            approved_requests = 0
            denied_requests = 0

            for parent_run_id in parent_run_ids:
                try:
                    all_requests = self.get_all_requests(parent_run_id)
                    total_requests += len(all_requests)
                    pending = self.get_pending_requests(parent_run_id)
                    pending_requests += len(pending)
                    for req in all_requests:
                        if req.status == ApprovalRequestStatus.APPROVED:
                            approved_requests += 1
                        elif req.status == ApprovalRequestStatus.DENIED:
                            denied_requests += 1
                except Exception as e:
                    logger.warning(f'Failed to get stats for {parent_run_id}: {e}')

            dashboard['requests'] = {
                'total': total_requests,
                'pending': pending_requests,
                'approved': approved_requests,
                'denied': denied_requests,
                'by_parent_run_id': len(parent_run_ids),
            }
        except Exception as e:
            logger.error(f'Failed to get request statistics: {e}')

        # Performance metrics
        try:
            if self._redis_store:
                redis_stats = self._redis_store.get_connection_stats()
                dashboard['performance']['redis'] = redis_stats

            slow_queries = (
                self._redis_store.get_slow_queries(limit=10)
                if self._redis_store
                else []
            )
            dashboard['performance']['slow_queries'] = len(slow_queries)
            dashboard['performance']['recent_slow_queries'] = slow_queries
        except Exception as e:
            logger.error(f'Failed to get performance metrics: {e}')

        # Security status
        try:
            if self.config.enable_security_monitoring:
                security_status = self.get_security_status()
                dashboard['security'] = security_status
        except Exception as e:
            logger.error(f'Failed to get security status: {e}')

        # Backend status
        dashboard['backend_status'] = {
            'redis_available': self._redis_available,
            'redis_primary': self.config.redis_primary,
            'file_primary': not self.config.redis_primary,
        }

        # Analytics
        try:
            analytics = self.get_analytics()
            dashboard['analytics'] = analytics
        except Exception as e:
            logger.error(f'Failed to get analytics: {e}')

        return dashboard

    def _create_notification(
        self,
        notification_type: str,
        message: str,
        request_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        severity: str = 'info',
    ) -> None:
        """Create a notification.

        Args:
            notification_type: Type of notification
            message: Notification message
            request_id: Related request ID
            parent_run_id: Related parent run ID
            severity: Notification severity
        """
        if not self.config.enable_notifications:
            return

        self._ensure_notifications()

        with self._lock:
            notification = {
                'timestamp': time.time(),
                'type': notification_type,
                'message': message,
                'request_id': request_id,
                'parent_run_id': parent_run_id,
                'severity': severity,
            }
            self._notifications.append(notification)
        logger.info(f'Notification: {notification_type} - {message}')

    def get_notifications(
        self,
        limit: int = 100,
        notification_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get notifications.

        Args:
            limit: Maximum number of notifications to return
            notification_type: Filter by notification type
            severity: Filter by severity

        Returns:
            List of notifications
        """
        filtered = self._notifications

        if notification_type:
            filtered = [n for n in filtered if n['type'] == notification_type]

        if severity:
            filtered = [n for n in filtered if n['severity'] == severity]

        return filtered[-limit:]

    def clear_notifications(
        self,
        notification_type: Optional[str] = None,
        older_than_seconds: Optional[int] = None,
    ) -> int:
        """Clear notifications.

        Args:
            notification_type: Clear only specific type
            older_than_seconds: Clear only notifications older than this

        Returns:
            Number of notifications cleared
        """
        if not self._notifications:
            return 0

        cutoff_time = time.time() - (older_than_seconds or 0)

        if notification_type:
            original_count = len(self._notifications)
            self._notifications = [
                n
                for n in self._notifications
                if n['type'] != notification_type
                or (older_than_seconds and n['timestamp'] < cutoff_time)
            ]
            return original_count - len(self._notifications)
        elif older_than_seconds:
            original_count = len(self._notifications)
            self._notifications = [
                n for n in self._notifications if n['timestamp'] >= cutoff_time
            ]
            return original_count - len(self._notifications)
        else:
            count = len(self._notifications)
            self._notifications.clear()
            return count

    def _policy_auto_approve_safe_operations(
        self, request: SubagentApprovalRequest
    ) -> bool:
        """Policy: Auto-approve safe read operations.

        Args:
            request: Request to evaluate

        Returns:
            True if should auto-approve
        """
        # Auto-approve read operations with no file modifications
        return (
            request.permission_mode == 'read'
            and request.isolation == 'none'
            and not any(
                arg.startswith('file://') for arg in str(request.tool_arguments).split()
            )
        )

    def _policy_auto_approve_low_risk_tools(
        self, request: SubagentApprovalRequest
    ) -> bool:
        """Policy: Auto-approve low-risk tools.

        Args:
            request: Request to evaluate

        Returns:
            True if should auto-approve
        """
        # Define low-risk tools
        low_risk_tools = {
            'read_file',
            'list_directory',
            'get_file_info',
            'search_files',
        }
        return request.tool_name in low_risk_tools

    def apply_approval_policies(
        self, parent_run_id: str, request: SubagentApprovalRequest
    ) -> bool:
        """Apply approval policies to a request.

        Args:
            parent_run_id: Parent run ID
            request: Request to evaluate

        Returns:
            True if request was auto-approved by a policy
        """
        if not self.config.enable_approval_policies:
            return False

        for policy_name, policy_func in self._approval_policies.items():
            try:
                if policy_func(request):
                    self.update_request_status(
                        parent_run_id,
                        request.request_id,
                        ApprovalRequestStatus.APPROVED,
                        approved_by=f'policy:{policy_name}',
                    )
                    self._create_notification(
                        'policy_auto_approval',
                        f'Request {request.request_id} auto-approved by policy {policy_name}',
                        request_id=request.request_id,
                        parent_run_id=parent_run_id,
                        severity='info',
                    )
                    logger.info(
                        f'Auto-approved request {request.request_id} by policy {policy_name}'
                    )
                    return True
            except Exception as e:
                logger.error(f'Policy {policy_name} failed: {e}')

        return False

    def add_approval_policy(
        self, name: str, policy_func: Callable[[SubagentApprovalRequest], bool]
    ) -> None:
        """Add a custom approval policy.

        Args:
            name: Policy name
            policy_func: Policy function that takes a request and returns bool
        """
        self._approval_policies[name] = policy_func
        logger.info(f'Added approval policy: {name}')

    def remove_approval_policy(self, name: str) -> bool:
        """Remove an approval policy.

        Args:
            name: Policy name

        Returns:
            True if policy was removed
        """
        if name in self._approval_policies:
            del self._approval_policies[name]
            logger.info(f'Removed approval policy: {name}')
            return True
        return False

    def get_approval_policies(self) -> list[str]:
        """Get list of active approval policies.

        Returns:
            List of policy names
        """
        return list(self._approval_policies.keys())

    def delegate_approval(
        self,
        parent_run_id: str,
        request_id: str,
        delegate_to: str,
        reason: str,
        delegated_by: str,
    ) -> bool:
        """Delegate approval of a request to another user.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            delegate_to: User to delegate to
            reason: Reason for delegation
            delegated_by: User who delegated

        Returns:
            True if delegation was successful
        """
        if not self.config.enable_delegation:
            return False

        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for delegation')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(f'Cannot delegate non-pending request {request_id}')
                return False

            # Record delegation
            self._delegations[request_id] = {
                'delegated_to': delegate_to,
                'delegated_by': delegated_by,
                'reason': reason,
                'timestamp': time.time(),
                'parent_run_id': parent_run_id,
            }

            self._create_notification(
                'approval_delegated',
                f'Request {request_id} delegated to {delegate_to} by {delegated_by}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Delegated request {request_id} to {delegate_to}')
            return True

        except Exception as e:
            logger.error(f'Failed to delegate request {request_id}: {e}')
            return False

    def get_delegation(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get delegation information for a request.

        Args:
            request_id: Request ID

        Returns:
            Delegation information or None
        """
        return self._delegations.get(request_id)

    def get_delegations_for_user(self, user: str) -> list[dict[str, Any]]:
        """Get all delegations for a specific user.

        Args:
            user: User to get delegations for

        Returns:
            List of delegation information
        """
        return [
            delegation
            for delegation in self._delegations.values()
            if delegation['delegated_to'] == user
        ]

    def clear_delegation(self, request_id: str) -> bool:
        """Clear delegation for a request.

        Args:
            request_id: Request ID

        Returns:
            True if delegation was cleared
        """
        if request_id in self._delegations:
            del self._delegations[request_id]
            logger.info(f'Cleared delegation for request {request_id}')
            return True
        return False

    def add_comment(
        self,
        parent_run_id: str,
        request_id: str,
        comment: str,
        author: str,
    ) -> bool:
        """Add a comment to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            comment: Comment text
            author: Comment author

        Returns:
            True if comment was added
        """
        if not self.config.enable_comments:
            return False

        try:
            self._ensure_comments()

            with self._lock:
                if request_id not in self._comments:
                    self._comments[request_id] = []

                self._comments[request_id].append(
                    {
                        'timestamp': time.time(),
                        'comment': comment,
                        'author': author,
                        'parent_run_id': parent_run_id,
                    }
                )

            self._create_notification(
                'comment_added',
                f'Comment added to request {request_id} by {author}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Comment added to request {request_id} by {author}')
            return True

        except Exception as e:
            logger.error(f'Failed to add comment to request {request_id}: {e}')
            return False

    def get_comments(self, request_id: str) -> list[dict[str, Any]]:
        """Get comments for a request.

        Args:
            request_id: Request ID

        Returns:
            List of comments
        """
        return self._comments.get(request_id, [])

    def delete_comment(self, request_id: str, comment_index: int) -> bool:
        """Delete a comment from a request.

        Args:
            request_id: Request ID
            comment_index: Index of comment to delete

        Returns:
            True if comment was deleted
        """
        if request_id in self._comments and 0 <= comment_index < len(
            self._comments[request_id]
        ):
            del self._comments[request_id][comment_index]
            logger.info(f'Deleted comment {comment_index} from request {request_id}')
            return True
        return False

    def get_approval_history(self, request_id: str) -> list[dict[str, Any]]:
        """Get approval history for a request.

        Args:
            request_id: Request ID

        Returns:
            List of history entries
        """
        return self._approval_history.get(request_id, [])

    def check_approval_quota(self, user: str) -> bool:
        """Check if user has remaining approval quota.

        Args:
            user: User to check

        Returns:
            True if user has quota remaining
        """
        if not self.config.enable_quota_management:
            return True

        remaining = self._approval_quotas.get(user, self.config.default_approval_quota)
        return remaining > 0

    def consume_approval_quota(self, user: str) -> bool:
        """Consume one approval from user's quota.

        Args:
            user: User to consume quota for

        Returns:
            True if quota was consumed
        """
        if not self.config.enable_quota_management:
            return True

        if not self.check_approval_quota(user):
            return False

        self._approval_quotas[user] = (
            self._approval_quotas.get(user, self.config.default_approval_quota) - 1
        )
        self._approval_counts[user] = self._approval_counts.get(user, 0) + 1

        self._create_notification(
            'quota_consumed',
            f'Approval quota consumed for user {user}',
            severity='info',
        )

        logger.info(f'Consumed approval quota for user {user}')
        return True

    def reset_approval_quota(self, user: str, quota: Optional[int] = None) -> None:
        """Reset approval quota for a user.

        Args:
            user: User to reset quota for
            quota: New quota (uses default if not specified)
        """
        if not self.config.enable_quota_management:
            return

        self._approval_quotas[user] = (
            quota if quota is not None else self.config.default_approval_quota
        )
        logger.info(
            f'Reset approval quota for user {user} to {self._approval_quotas[user]}'
        )

    def get_quota_status(self, user: str) -> dict[str, Any]:
        """Get quota status for a user.

        Args:
            user: User to get status for

        Returns:
            Dictionary with quota status
        """
        if not self.config.enable_quota_management:
            return {'enabled': False}

        return {
            'enabled': True,
            'remaining': self._approval_quotas.get(
                user, self.config.default_approval_quota
            ),
            'total': self.config.default_approval_quota,
            'used': self._approval_counts.get(user, 0),
        }

    def create_workflow_chain(self, name: str, required_approvers: list[str]) -> bool:
        """Create a multi-step approval workflow chain.

        Args:
            name: Workflow name
            required_approvers: List of required approvers in order

        Returns:
            True if workflow was created
        """
        if not self.config.enable_workflow_chains:
            return False

        self._workflow_chains[name] = required_approvers
        logger.info(
            f'Created workflow chain {name} with {len(required_approvers)} required approvers'
        )
        return True

    def assign_reviewer(
        self, parent_run_id: str, request_id: str, reviewer: str
    ) -> bool:
        """Assign a reviewer to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            reviewer: Reviewer to assign

        Returns:
            True if reviewer was assigned
        """
        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for reviewer assignment')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(
                    f'Cannot assign reviewer to non-pending request {request_id}'
                )
                return False

            self._reviewer_assignments[request_id] = reviewer

            self._create_notification(
                'reviewer_assigned',
                f'Reviewer {reviewer} assigned to request {request_id}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Assigned reviewer {reviewer} to request {request_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to assign reviewer to request {request_id}: {e}')
            return False

    def get_assigned_reviewer(self, request_id: str) -> Optional[str]:
        """Get assigned reviewer for a request.

        Args:
            request_id: Request ID

        Returns:
            Assigned reviewer or None
        """
        return self._reviewer_assignments.get(request_id)

    def create_approval_template(
        self,
        name: str,
        required_approvers: list[str],
        auto_approve_threshold: int = 1,
        timeout_seconds: int = 3600,
    ) -> bool:
        """Create an approval template.

        Args:
            name: Template name
            required_approvers: List of required approvers
            auto_approve_threshold: Number of approvals needed for auto-approval
            timeout_seconds: Timeout for template

        Returns:
            True if template was created
        """
        self._approval_templates[name] = {
            'required_approvers': required_approvers,
            'auto_approve_threshold': auto_approve_threshold,
            'timeout_seconds': timeout_seconds,
            'created_at': time.time(),
        }
        logger.info(f'Created approval template {name}')
        return True

    def apply_approval_template(
        self,
        parent_run_id: str,
        request_id: str,
        template_name: str,
    ) -> bool:
        """Apply an approval template to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            template_name: Template to apply

        Returns:
            True if template was applied
        """
        if template_name not in self._approval_templates:
            logger.error(f'Template {template_name} not found')
            return False

        template = self._approval_templates[template_name]

        # Assign required reviewers
        for reviewer in template['required_approvers']:
            self.assign_reviewer(parent_run_id, request_id, reviewer)

        self._create_notification(
            'template_applied',
            f'Template {template_name} applied to request {request_id}',
            request_id=request_id,
            parent_run_id=parent_run_id,
            severity='info',
        )

        logger.info(f'Applied template {template_name} to request {request_id}')
        return True

    def add_tag(self, parent_run_id: str, request_id: str, tag: str) -> bool:
        """Add a tag to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            tag: Tag to add

        Returns:
            True if tag was added
        """
        if not self.config.enable_tagging:
            return False

        try:
            if request_id not in self._request_tags:
                self._request_tags[request_id] = set()

            self._request_tags[request_id].add(tag)

            self._create_notification(
                'tag_added',
                f'Tag {tag} added to request {request_id}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Added tag {tag} to request {request_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to add tag to request {request_id}: {e}')
            return False

    def remove_tag(self, request_id: str, tag: str) -> bool:
        """Remove a tag from a request.

        Args:
            request_id: Request ID
            tag: Tag to remove

        Returns:
            True if tag was removed
        """
        if request_id in self._request_tags and tag in self._request_tags[request_id]:
            self._request_tags[request_id].remove(tag)
            logger.info(f'Removed tag {tag} from request {request_id}')
            return True
        return False

    def get_tags(self, request_id: str) -> set[str]:
        """Get tags for a request.

        Args:
            request_id: Request ID

        Returns:
            Set of tags
        """
        return self._request_tags.get(request_id, set())

    def search_by_tag(self, tag: str) -> list[str]:
        """Search for requests by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of request IDs with the tag
        """
        return [
            request_id for request_id, tags in self._request_tags.items() if tag in tags
        ]

    def cast_vote(
        self,
        parent_run_id: str,
        request_id: str,
        voter: str,
        vote: bool,  # True = approve, False = deny
    ) -> bool:
        """Cast a vote on a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            voter: Voter identifier
            vote: Vote (True=approve, False=deny)

        Returns:
            True if vote was cast
        """
        if not self.config.enable_voting:
            return False

        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for voting')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(f'Cannot vote on non-pending request {request_id}')
                return False

            self._ensure_votes()

            with self._lock:
                if request_id not in self._votes:
                    self._votes[request_id] = {}

                self._votes[request_id][voter] = vote

            self._create_notification(
                'vote_cast',
                f'Vote cast by {voter} on request {request_id}: {"approve" if vote else "deny"}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(
                f'Vote cast by {voter} on request {request_id}: {"approve" if vote else "deny"}'
            )

            # Auto-approve if vote threshold reached (simple majority)
            vote_summary = self.get_vote_summary(request_id)
            if vote_summary.get('total_votes', 0) >= 2:  # Need at least 2 voters
                approve_count = vote_summary.get('approve_count', 0)
                total = vote_summary.get('total_votes', 0)
                if approve_count > total / 2:  # Majority approves
                    logger.info(
                        f'Auto-approving request {request_id} based on majority vote ({approve_count}/{total})'
                    )
                    self.update_request_status(
                        parent_run_id,
                        request_id,
                        ApprovalRequestStatus.APPROVED,
                        approved_by='auto-approval-vote',
                        reason=f'Auto-approved by majority vote ({approve_count}/{total})',
                    )

            return True

        except Exception as e:
            logger.error(f'Failed to cast vote on request {request_id}: {e}')
            return False

    def get_votes(self, request_id: str) -> dict[str, bool]:
        """Get votes for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary of votes {voter: vote}
        """
        if self._votes is None:
            return {}
        return self._votes.get(request_id, {})

    def get_vote_summary(self, request_id: str) -> dict[str, Any]:
        """Get vote summary for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary with vote summary
        """
        if self._votes is None:
            return {'total_votes': 0, 'approve_count': 0, 'deny_count': 0, 'votes': {}}

        votes = self._votes.get(request_id, {})
        approve_count = sum(1 for v in votes.values() if v)
        deny_count = sum(1 for v in votes.values() if not v)

        return {
            'total_votes': len(votes),
            'approve_count': approve_count,
            'deny_count': deny_count,
            'votes': votes,
        }

    def send_reminder(
        self,
        parent_run_id: str,
        request_id: str,
        recipient: str,
    ) -> bool:
        """Send a reminder for a pending request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            recipient: Recipient of the reminder

        Returns:
            True if reminder was sent
        """
        if not self.config.enable_reminders:
            return False

        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for reminder')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(
                    f'Cannot send reminder for non-pending request {request_id}'
                )
                return False

            if request_id not in self._reminders:
                self._reminders[request_id] = []

            self._reminders[request_id].append(time.time())

            self._create_notification(
                'reminder_sent',
                f'Reminder sent to {recipient} for request {request_id}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Reminder sent to {recipient} for request {request_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to send reminder for request {request_id}: {e}')
            return False

    def get_reminders(self, request_id: str) -> list[float]:
        """Get reminder timestamps for a request.

        Args:
            request_id: Request ID

        Returns:
            List of reminder timestamps
        """
        return self._reminders.get(request_id, [])

    def generate_audit_report(
        self,
        parent_run_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Generate a comprehensive audit report for a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID

        Returns:
            Dictionary with audit report
        """
        if not self.config.enable_audit_reports:
            return {'enabled': False}

        report = {
            'timestamp': time.time(),
            'request_id': request_id,
            'parent_run_id': parent_run_id,
        }

        # Request details
        request = self.get_request(parent_run_id, request_id)
        if request:
            report['request'] = {
                'subagent_id': request.subagent_id,
                'tool_name': request.tool_name,
                'status': request.status.value,
                'created_at': request.created_at.isoformat(),
                'updated_at': request.updated_at.isoformat()
                if request.updated_at
                else None,
            }

        # Approval history
        report['approval_history'] = self.get_approval_history(request_id)

        # Comments
        report['comments'] = self.get_comments(request_id)

        # Votes
        report['votes'] = self.get_vote_summary(request_id)

        # Delegation
        delegation = self.get_delegation(request_id)
        if delegation:
            report['delegation'] = delegation

        # Escalation
        if request_id in self._escalations:
            report['escalation'] = self._escalations[request_id]

        # Tags
        report['tags'] = list(self.get_tags(request_id))

        # Reminders
        report['reminders'] = self.get_reminders(request_id)

        # Reviewer assignment
        reviewer = self.get_assigned_reviewer(request_id)
        if reviewer:
            report['assigned_reviewer'] = reviewer

        # Audit trail entries
        report['audit_trail'] = self.get_audit_trail(parent_run_id, request_id)

        return report

    def generate_summary_report(self) -> dict[str, Any]:
        """Generate a summary report of all requests.

        Returns:
            Dictionary with summary report
        """
        if not self.config.enable_audit_reports:
            return {'enabled': False}

        report = {
            'timestamp': time.time(),
            'summary': {},
        }

        try:
            parent_run_ids = self.list_parent_run_ids()
            total_requests = 0
            pending_requests = 0
            approved_requests = 0
            denied_requests = 0

            for parent_run_id in parent_run_ids:
                try:
                    all_requests = self.get_all_requests(parent_run_id)
                    total_requests += len(all_requests)
                    pending = self.get_pending_requests(parent_run_id)
                    pending_requests += len(pending)
                    for req in all_requests:
                        if req.status == ApprovalRequestStatus.APPROVED:
                            approved_requests += 1
                        elif req.status == ApprovalRequestStatus.DENIED:
                            denied_requests += 1
                except Exception as e:
                    logger.warning(f'Failed to get summary for {parent_run_id}: {e}')

            report['summary'] = {
                'total_requests': total_requests,
                'pending_requests': pending_requests,
                'approved_requests': approved_requests,
                'denied_requests': denied_requests,
                'parent_run_ids': len(parent_run_ids),
            }

            # Analytics
            report['analytics'] = self.get_analytics()

            # Dashboard
            report['dashboard'] = self.get_statistics_dashboard()

        except Exception as e:
            logger.error(f'Failed to generate summary report: {e}')
            report['error'] = str(e)

        return report

    def set_sla_deadline(self, request_id: str, deadline_seconds: int) -> bool:
        """Set SLA deadline for a request.

        Args:
            request_id: Request ID
            deadline_seconds: Deadline in seconds from now

        Returns:
            True if deadline was set
        """
        if not self.config.enable_sla_tracking:
            return False

        self._ensure_sla_deadlines()

        self._sla_deadlines[request_id] = time.time() + deadline_seconds
        logger.info(
            f'SLA deadline set for request {request_id}: {deadline_seconds} seconds'
        )
        return True

    def check_sla_compliance(self, request_id: str) -> dict[str, Any]:
        """Check SLA compliance for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary with SLA status
        """
        if not self.config.enable_sla_tracking:
            return {'enabled': False}

        self._ensure_sla_deadlines()

        if request_id not in self._sla_deadlines:
            return {'enabled': True, 'is_compliant': True, 'overdue_by': 0}

        deadline = self._sla_deadlines[request_id]
        current_time = time.time()
        remaining = deadline - current_time

        return {
            'enabled': True,
            'deadline': deadline,
            'remaining_seconds': remaining,
            'is_compliant': remaining > 0,
            'overdue_by': -remaining if remaining < 0 else 0,
        }

    def add_approval_condition(
        self, name: str, condition_func: Callable[[SubagentApprovalRequest], bool]
    ) -> None:
        """Add an approval condition.

        Args:
            name: Condition name
            condition_func: Function that evaluates the condition
        """
        if self.config.enable_conditions:
            self._approval_conditions[name] = condition_func
            logger.info(f'Added approval condition: {name}')

    def check_approval_conditions(
        self, request: SubagentApprovalRequest
    ) -> dict[str, bool]:
        """Check all approval conditions for a request.

        Args:
            request: Request to check

        Returns:
            Dictionary of condition results
        """
        if not self.config.enable_conditions:
            return {}

        results = {}
        for name, condition_func in self._approval_conditions.items():
            try:
                results[name] = condition_func(request)
            except Exception as e:
                logger.error(f'Condition {name} failed: {e}')
                results[name] = False

        return results

    def add_dependency(self, request_id: str, depends_on: str) -> bool:
        """Add a dependency between requests.

        Args:
            request_id: Request ID
            depends_on: Request ID this depends on

        Returns:
            True if dependency was added
        """
        if not self.config.enable_dependencies:
            return False

        self._ensure_dependencies()

        if request_id not in self._dependencies:
            self._dependencies[request_id] = []

        if depends_on not in self._dependencies[request_id]:
            self._dependencies[request_id].append(depends_on)
            logger.info(f'Added dependency: {request_id} depends on {depends_on}')
            return True

        return False

    def check_dependencies(self, request_id: str, parent_run_id: str) -> dict[str, Any]:
        """Check if dependencies are satisfied.

        Args:
            request_id: Request ID
            parent_run_id: Parent run ID

        Returns:
            Dictionary with dependency status
        """
        if not self.config.enable_dependencies:
            return {'enabled': False}

        self._ensure_dependencies()

        if request_id not in self._dependencies:
            return {'enabled': True, 'all_satisfied': True, 'unsatisfied_ids': []}

        dependencies = self._dependencies.get(request_id, [])
        satisfied = []
        unsatisfied = []

        for dep_id in dependencies:
            dep_request = self.get_request(parent_run_id, dep_id)
            if dep_request and dep_request.status == ApprovalRequestStatus.APPROVED:
                satisfied.append(dep_id)
            else:
                unsatisfied.append(dep_id)

        return {
            'enabled': True,
            'total': len(dependencies),
            'satisfied': len(satisfied),
            'unsatisfied': len(unsatisfied),
            'satisfied_ids': satisfied,
            'unsatisfied_ids': unsatisfied,
            'all_satisfied': len(unsatisfied) == 0,
        }

    def set_priority_escalation_rule(
        self, priority: str, threshold_seconds: int
    ) -> bool:
        """Set priority-based escalation rule.

        Args:
            priority: Priority level
            threshold_seconds: Escalation threshold in seconds

        Returns:
            True if rule was set
        """
        if not self.config.enable_priority_escalation:
            return False

        self._priority_escalation_rules[priority] = threshold_seconds
        logger.info(f'Set priority escalation rule: {priority} -> {threshold_seconds}s')
        return True

    def check_priority_escalation(
        self, request: SubagentApprovalRequest
    ) -> Optional[int]:
        """Check if request should be escalated based on priority.

        Args:
            request: Request to check

        Returns:
            Escalation threshold or None
        """
        if not self.config.enable_priority_escalation:
            return None

        return self._priority_escalation_rules.get(request.priority)

    def add_validation_rule(
        self,
        name: str,
        rule_func: Callable[[SubagentApprovalRequest], tuple[bool, str]],
    ) -> None:
        """Add a validation rule.

        Args:
            name: Rule name
            rule_func: Function that validates and returns (is_valid, error_message)
        """
        if self.config.enable_validation_rules:
            self._validation_rules[name] = rule_func
            logger.info(f'Added validation rule: {name}')

    def apply_validation_rules(
        self, request: SubagentApprovalRequest
    ) -> dict[str, Any]:
        """Apply all validation rules to a request.

        Args:
            request: Request to validate

        Returns:
            Dictionary with validation results
        """
        if not self.config.enable_validation_rules:
            return {'enabled': False}

        results = {
            'enabled': True,
            'is_valid': True,
            'errors': [],
        }

        for name, rule_func in self._validation_rules.items():
            try:
                is_valid, error_message = rule_func(request)
                if not is_valid:
                    results['is_valid'] = False
                    results['errors'].append(f'{name}: {error_message}')
            except Exception as e:
                results['is_valid'] = False
                results['errors'].append(f'{name}: {str(e)}')

        return results

    def sign_request(self, request_id: str, signer: str, signature: str) -> bool:
        """Sign a request with approval signature.

        Args:
            request_id: Request ID
            signer: Signer identifier
            signature: Signature data

        Returns:
            True if signature was added
        """
        if not self.config.enable_signatures:
            return False

        self._signatures[request_id] = {
            'signer': signer,
            'signature': signature,
            'timestamp': time.time(),
        }
        logger.info(f'Request {request_id} signed by {signer}')
        return True

    def get_signature(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get signature for a request.

        Args:
            request_id: Request ID

        Returns:
            Signature info or None
        """
        return self._signatures.get(request_id)

    def create_version(self, request_id: str, request_data: dict[str, Any]) -> bool:
        """Create a new version of a request.

        Args:
            request_id: Request ID
            request_data: Request data

        Returns:
            True if version was created
        """
        if not self.config.enable_versioning:
            return False

        if request_id not in self._versions:
            self._versions[request_id] = []

        version = {
            'version': len(self._versions[request_id]) + 1,
            'timestamp': time.time(),
            'data': request_data,
        }

        self._versions[request_id].append(version)
        logger.info(f'Created version {version["version"]} for request {request_id}')
        return True

    def get_versions(self, request_id: str) -> list[dict[str, Any]]:
        """Get all versions of a request.

        Args:
            request_id: Request ID

        Returns:
            List of versions
        """
        return self._versions.get(request_id, [])

    def detect_conflict(
        self, request_id: str, conflict_type: str, details: dict[str, Any]
    ) -> bool:
        """Detect and record a conflict.

        Args:
            request_id: Request ID
            conflict_type: Type of conflict
            details: Conflict details

        Returns:
            True if conflict was recorded
        """
        if not self.config.enable_conflict_resolution:
            return False

        self._conflicts[request_id] = {
            'type': conflict_type,
            'details': details,
            'timestamp': time.time(),
            'resolved': False,
        }
        logger.warning(f'Conflict detected for request {request_id}: {conflict_type}')
        return True

    def resolve_conflict(self, request_id: str, resolution: str) -> bool:
        """Resolve a conflict.

        Args:
            request_id: Request ID
            resolution: Resolution description

        Returns:
            True if conflict was resolved
        """
        if request_id in self._conflicts:
            self._conflicts[request_id]['resolved'] = True
            self._conflicts[request_id]['resolution'] = resolution
            self._conflicts[request_id]['resolved_at'] = time.time()
            logger.info(f'Conflict resolved for request {request_id}: {resolution}')
            return True
        return False

    def get_conflict(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get conflict info for a request.

        Args:
            request_id: Request ID

        Returns:
            Conflict info or None
        """
        return self._conflicts.get(request_id)

    def record_performance_metric(
        self, request_id: str, metric_name: str, value: float
    ) -> bool:
        """Record a performance metric for a request.

        Args:
            request_id: Request ID
            metric_name: Metric name
            value: Metric value

        Returns:
            True if metric was recorded
        """
        if not self.config.enable_performance_metrics:
            return False

        self._ensure_performance_metrics()

        if request_id not in self._performance_metrics:
            self._performance_metrics[request_id] = {}

        self._performance_metrics[request_id][metric_name] = value
        return True

    def get_performance_metrics(self, request_id: str) -> dict[str, float]:
        """Get performance metrics for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary of metrics
        """
        return self._performance_metrics.get(request_id, {})

    def add_compliance_rule(
        self,
        name: str,
        rule_func: Callable[[SubagentApprovalRequest], tuple[bool, str]],
    ) -> None:
        """Add a compliance rule.

        Args:
            name: Rule name
            rule_func: Function that checks compliance
        """
        if self.config.enable_compliance_checks:
            self._compliance_rules[name] = rule_func
            logger.info(f'Added compliance rule: {name}')

    def check_compliance(self, request: SubagentApprovalRequest) -> dict[str, Any]:
        """Check compliance for a request.

        Args:
            request: Request to check

        Returns:
            Dictionary with compliance results
        """
        if not self.config.enable_compliance_checks:
            return {'enabled': False}

        results = {
            'enabled': True,
            'is_compliant': True,
            'violations': [],
        }

        for name, rule_func in self._compliance_rules.items():
            try:
                is_compliant, message = rule_func(request)
                if not is_compliant:
                    results['is_compliant'] = False
                    results['violations'].append(f'{name}: {message}')
            except Exception as e:
                results['is_compliant'] = False
                results['violations'].append(f'{name}: {str(e)}')

        return results

    def reset_analytics(self) -> None:
        """Reset analytics data."""
        self._analytics = {
            'total_requests': 0,
            'approved_requests': 0,
            'denied_requests': 0,
            'cancelled_requests': 0,
            'pending_requests': 0,
            'by_subagent': {},
            'by_tool': {},
            'approval_rate': 0.0,
            'average_approval_time_seconds': 0.0,
        }

    def shutdown(self, timeout: float = 30.0) -> dict[str, Any]:
        """Gracefully shutdown the hybrid queue.

        Args:
            timeout: Maximum time to wait for shutdown (seconds)

        Returns:
            Dictionary with shutdown status
        """
        logger.info('Shutting down hybrid approval queue')

        # Persist state before shutdown
        self._persist_state_to_file()

        # Close Redis connection if available
        if self._redis_store and self._redis_store.redis_client:
            try:
                self._redis_store.redis_client.close()
                logger.info('Closed Redis connection')
            except Exception as e:
                logger.error(f'Failed to close Redis connection: {e}')

        # Clear cache if available
        if self._redis_store:
            try:
                self._redis_store._clear_cache()
                logger.info('Cleared cache')
            except Exception as e:
                logger.error(f'Failed to clear cache: {e}')

        logger.info('Hybrid approval queue shutdown complete')
        return {
            'timestamp': time.time(),
            'success': True,
        }

    def get_audit_trail(
        self,
        parent_run_id: Optional[str] = None,
        request_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail entries."""
        if not self.config.enable_audit_trail:
            return []

        filtered = self._audit_trail
        if parent_run_id:
            filtered = [e for e in filtered if e['parent_run_id'] == parent_run_id]
        if request_id:
            filtered = [e for e in filtered if e['request_id'] == request_id]

        return filtered[-limit:]

    def cancel_request(self, parent_run_id: str, request_id: str, reason: str) -> bool:
        """Cancel a pending request."""
        try:
            snapshot = self._file_store.load(parent_run_id)
            if request_id not in snapshot.requests:
                logger.warning(f'Request {request_id} not found for cancellation')
                return False

            request_data = snapshot.requests[request_id]
            if request_data.get('status') != 'pending':
                logger.warning(
                    f'Cannot cancel non-pending request {request_id}: {request_data.get("status")}'
                )
                return False

            # Update status to cancelled
            request_data['status'] = 'cancelled'
            request_data['cancelled_at'] = time.time()
            request_data['cancellation_reason'] = reason

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            # Add audit entry
            self._add_audit_entry(
                'cancel_request',
                parent_run_id,
                request_id,
                {'reason': reason},
                correlation_id=self.config.correlation_id or request_id,
            )

            logger.info(f'Cancelled request {request_id}: {reason}')
            return True
        except Exception as e:
            logger.error(f'Failed to cancel request {request_id}: {e}')
            return False

    def search_requests(
        self,
        parent_run_id: str,
        *,
        subagent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[SubagentApprovalRequest]:
        """Search and filter requests."""
        try:
            snapshot = self._file_store.load(parent_run_id)
            results = []

            for _request_id, request_data in snapshot.requests.items():
                # Apply filters
                if subagent_id and request_data.get('subagent_id') != subagent_id:
                    continue
                if tool_name and request_data.get('tool_name') != tool_name:
                    continue
                if status and request_data.get('status') != status:
                    continue

                from teaagent.subagents._approval_queue_store import (
                    request_from_dict,
                )

                results.append(request_from_dict(request_data))

                if len(results) >= limit:
                    break

            return results
        except Exception as e:
            logger.error(f'Failed to search requests: {e}')
            return []

    def export_requests(self, parent_run_id: str, format: str = 'json') -> str:
        """Export requests from a parent run."""
        try:
            snapshot = self._file_store.load(parent_run_id)

            if format == 'json':
                return json.dumps(
                    {
                        'parent_run_id': parent_run_id,
                        'requests': snapshot.requests,
                        'batches': snapshot.batches,
                        'exported_at': time.time(),
                    },
                    indent=2,
                )
            else:
                raise ValueError(f'Unsupported export format: {format}')
        except Exception as e:
            logger.error(f'Failed to export requests: {e}')
            raise

    def import_requests(
        self, parent_run_id: str, data: str, format: str = 'json'
    ) -> int:
        """Import requests to a parent run."""
        try:
            if format == 'json':
                import_data = json.loads(data)
            else:
                raise ValueError(f'Unsupported import format: {format}')

            # Load existing snapshot
            snapshot = self._file_store.load(parent_run_id)

            # Merge requests
            imported_count = 0
            for request_id, request_data in import_data.get('requests', {}).items():
                if request_id not in snapshot.requests:
                    snapshot.requests[request_id] = request_data
                    imported_count += 1

            # Merge batches
            for batch_id, batch_data in import_data.get('batches', {}).items():
                if batch_id not in snapshot.batches:
                    snapshot.batches[batch_id] = batch_data

            # Save back
            with self._file_store.lock(parent_run_id):
                self._file_store._save_unlocked(parent_run_id, snapshot)

            logger.info(f'Imported {imported_count} requests to {parent_run_id}')
            return imported_count
        except Exception as e:
            logger.error(f'Failed to import requests: {e}')
            raise

    def archive_old_requests(self, max_age_days: int = 30) -> dict[str, Any]:
        """Archive old requests to separate storage."""
        if not self.config.enable_archival:
            logger.warning('Archival not enabled')
            return {'archived': 0, 'errors': 0, 'archived_requests': []}

        archive_report: dict[str, Any] = {
            'archived': 0,
            'errors': 0,
            'archived_requests': [],
        }

        try:
            parent_run_ids = self.list_parent_run_ids()
            max_age_seconds = max_age_days * 86400

            for parent_run_id in parent_run_ids:
                try:
                    snapshot = self._file_store.load(parent_run_id)
                    current_time = time.time()

                    for _request_id, request_data in list(snapshot.requests.items()):
                        created_at = request_data.get('created_at', '')
                        if not created_at:
                            continue

                        try:
                            from datetime import datetime

                            created_time = datetime.fromisoformat(created_at)
                            age_seconds = current_time - created_time.timestamp()

                            if age_seconds > max_age_seconds:
                                # Archive request
                                archive_data = {
                                    'request_id': _request_id,
                                    'request_data': request_data,
                                    'archived_at': current_time,
                                    'parent_run_id': parent_run_id,
                                }

                                # Add to archive (in practice, this would go to separate storage)
                                archive_report['archived_requests'].append(archive_data)

                                # Remove from active queue
                                del snapshot.requests[_request_id]
                                archive_report['archived'] += 1

                        except Exception as e:
                            logger.warning(
                                f'Failed to archive request {_request_id}: {e}'
                            )
                            archive_report['errors'] += 1

                    # Save updated snapshot
                    if archive_report['archived'] > 0:
                        with self._file_store.lock(parent_run_id):
                            self._file_store._save_unlocked(parent_run_id, snapshot)

                except Exception as e:
                    logger.error(f'Failed to archive requests for {parent_run_id}: {e}')
                    archive_report['errors'] += 1

            logger.info(f'Archived {archive_report["archived"]} requests')
            return archive_report
        except Exception as e:
            logger.error(f'Failed to archive old requests: {e}')
            archive_report['errors'] += 1
            return archive_report
