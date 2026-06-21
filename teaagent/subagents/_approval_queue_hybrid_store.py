"""Hybrid approval queue store combining file-based and Redis backends."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from cryptography.fernet import Fernet

from teaagent.subagents._approval_queue import (
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_metrics import (
    BackendType,
    get_metrics_collector,
)
from teaagent.subagents._approval_queue_redis_store import (
    RedisApprovalQueueConfig,
    RedisApprovalQueueStore,
)
from teaagent.subagents._approval_queue_store import (
    ApprovalQueueStore,
    default_hmac_secret,
)
from teaagent.subagents._circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from teaagent.subagents._feature_flags import FeatureFlags
from teaagent.subagents._hybrid_store_backends import HybridStoreBackendsMixin

# Mixin imports — each provides a focused domain of operations
from teaagent.subagents._hybrid_store_crud import HybridStoreCrudMixin
from teaagent.subagents._hybrid_store_governance import HybridStoreGovernanceMixin
from teaagent.subagents._hybrid_store_health import HybridStoreHealthMixin
from teaagent.subagents._hybrid_store_migration import HybridStoreMigrationMixin
from teaagent.subagents._hybrid_store_safety import HybridStoreSafetyMixin
from teaagent.subagents._hybrid_store_social import HybridStoreSocialMixin
from teaagent.subagents._hybrid_store_workflow import HybridStoreWorkflowMixin
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


class HybridApprovalQueueStore(
    HybridStoreCrudMixin,
    HybridStoreBackendsMixin,
    HybridStoreMigrationMixin,
    HybridStoreSafetyMixin,
    HybridStoreHealthMixin,
    HybridStoreGovernanceMixin,
    HybridStoreSocialMixin,
    HybridStoreWorkflowMixin,
):
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
        self._analytics: dict[str, Any] = {}

        # Notification system (lazy init)
        self._notifications: list[dict[str, Any]] = []

        # Approval policies (always init, these are config-driven)
        self._approval_policies: dict[
            str, Callable[[SubagentApprovalRequest], bool]
        ] = {
            'auto_approve_safe_operations': self._policy_auto_approve_safe_operations,
            'auto_approve_low_risk_tools': self._policy_auto_approve_low_risk_tools,
        }

        # Delegation system (lazy init)
        self._delegations: dict[str, dict[str, Any]] = {}

        # Escalation system (lazy init)
        self._escalations: dict[str, dict[str, Any]] = {}

        # Comments system (lazy init)
        self._comments: dict[str, list[dict[str, Any]]] = {}

        # Approval history (lazy init)
        self._approval_history: dict[str, list[dict[str, Any]]] = {}

        # Quota management (always init, needed for quota checks)
        self._approval_quotas: dict[str, int] = {}
        self._approval_counts: dict[str, int] = {}

        # Workflow chains (always init, config-driven)
        self._workflow_chains: dict[str, list[str]] = {}

        # Reviewer assignment (lazy init)
        self._reviewer_assignments: dict[str, str] = {}

        # Approval templates (always init, config-driven)
        self._approval_templates: dict[str, dict[str, Any]] = {}

        # Request tags (lazy init)
        self._request_tags: dict[str, set[str]] = {}

        # Voting system (lazy init)
        self._votes: dict[str, dict[str, bool]] = {}

        # Reminder system (lazy init)
        self._reminders: dict[str, list[float]] = {}

        # SLA tracking (lazy init)
        self._sla_deadlines: dict[str, float] = {}

        # Approval conditions (always init, config-driven)
        self._approval_conditions: dict[
            str, Callable[[SubagentApprovalRequest], bool]
        ] = {}

        # Request dependencies (lazy init)
        self._dependencies: dict[str, list[str]] = {}

        # Priority escalation (always init, config-driven)
        self._priority_escalation_rules: dict[str, int] = {}

        # Validation rules (always init, config-driven)
        self._validation_rules: dict[
            str, Callable[[SubagentApprovalRequest], tuple[bool, str]]
        ] = {}

        # Signatures (lazy init)
        self._signatures: dict[str, dict[str, Any]] = {}

        # Versioning (lazy init)
        self._versions: dict[str, list[dict[str, Any]]] = {}

        # Conflict resolution (lazy init)
        self._conflicts: dict[str, dict[str, Any]] = {}

        # Performance metrics (lazy init)
        self._performance_metrics: dict[str, dict[str, float]] = {}

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
