"""Base class declaring shared attributes for hybrid store mixins.

This file exists solely to provide mypy with class-level type annotations
for attributes that are initialized in the facade's __init__ but accessed
from mixin classes. Mixins inherit from this base so mypy can resolve
``self.xxx`` attribute types.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from teaagent.subagents._approval_queue import SubagentApprovalRequest
    from teaagent.subagents._approval_queue_hybrid_store import (
        HybridApprovalQueueConfig,
    )
    from teaagent.subagents._approval_queue_metrics import (
        ApprovalQueueMetrics,
        MetricsCollector,
    )
    from teaagent.subagents._approval_queue_redis_store import (
        RedisApprovalQueueStore,
    )
    from teaagent.subagents._approval_queue_store import ApprovalQueueStore
    from teaagent.subagents._circuit_breaker import CircuitBreaker
    from teaagent.subagents._feature_flags import FeatureFlags
    from teaagent.subagents._prometheus_metrics import PrometheusMetricsExporter


class HybridStoreBase:
    config: HybridApprovalQueueConfig
    _feature_flags: FeatureFlags

    _file_store: ApprovalQueueStore
    _redis_store: Optional[RedisApprovalQueueStore]
    _redis_client: Optional[Any]
    _redis_available: bool

    _circuit_breaker: Optional[CircuitBreaker]

    _metrics_collector: MetricsCollector
    _metrics: ApprovalQueueMetrics

    _request_hashes: dict[str, float]
    _deduplication_lock: Optional[Any]
    _rate_limit_tracker: defaultdict[str, list[float]]

    _audit_trail: list[dict[str, Any]]
    _security_events: list[dict[str, Any]]
    _security_alerts: list[dict[str, Any]]
    _prometheus_exporter: PrometheusMetricsExporter
    _encryption_key: Optional[bytes]
    _cipher: Optional[Fernet]

    _state_lock: threading.RLock
    _lock: threading.RLock

    _sync_errors: int
    _max_sync_errors: int
    _current_sync_interval: int
    _last_sync_time: float
    _operation_latencies: list[float]
    _max_latency_samples: int

    _analytics: dict[str, Any]
    _notifications: list[dict[str, Any]]

    _approval_policies: dict[str, Callable[[SubagentApprovalRequest], bool]]
    _approval_conditions: dict[str, Callable[[SubagentApprovalRequest], bool]]
    _validation_rules: dict[str, Callable[[SubagentApprovalRequest], tuple[bool, str]]]
    _compliance_rules: dict[str, Callable[[SubagentApprovalRequest], tuple[bool, str]]]

    _delegations: dict[str, dict[str, Any]]
    _escalations: dict[str, dict[str, Any]]

    _comments: dict[str, list[dict[str, Any]]]
    _approval_history: dict[str, list[dict[str, Any]]]

    _approval_quotas: dict[str, int]
    _approval_counts: dict[str, int]

    _workflow_chains: dict[str, list[str]]
    _reviewer_assignments: dict[str, str]
    _approval_templates: dict[str, dict[str, Any]]

    _request_tags: dict[str, set[str]]
    _votes: dict[str, dict[str, bool]]
    _reminders: dict[str, list[float]]

    _sla_deadlines: dict[str, float]
    _dependencies: dict[str, list[str]]
    _priority_escalation_rules: dict[str, int]

    _signatures: dict[str, dict[str, Any]]
    _versions: dict[str, list[dict[str, Any]]]
    _conflicts: dict[str, dict[str, Any]]
    _performance_metrics: dict[str, dict[str, float]]

    # ═══ Cross-mixin method stubs ═══

    def save_request(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_request(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_all_requests(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_pending_requests(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def list_parent_run_ids(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def update_request_status(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def delete_parent_run(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def delete(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _check_redis_available(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _call_redis(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_metrics(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_circuit_breaker_stats(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _compress_data(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _encrypt_data(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _decrypt_data(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _decompress_data(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _add_audit_entry(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _record_security_event(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _check_rate_limit(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _is_duplicate_request(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_security_status(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_audit_trail(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_analytics(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _create_notification(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_comments(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_vote_summary(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_tags(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_reminders(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def apply_approval_policies(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def check_approval_quota(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def check_compliance(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def check_dependencies(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_delegation(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def record_performance_metric(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_statistics_dashboard(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def sign_request(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def export_requests(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def comprehensive_health_check(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def validate_global_consistency(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _persist_state_to_file(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_analytics(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_notifications(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_comments(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_votes(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_dependencies(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_performance_metrics(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_sla_deadlines(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_escalations(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def _ensure_approval_history(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def get_approval_history(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError

    def validate_request(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG002
        raise NotImplementedError
