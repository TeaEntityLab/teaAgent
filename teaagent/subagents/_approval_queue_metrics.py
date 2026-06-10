"""Metrics and monitoring for approval queue operations."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of approval queue operations."""

    SAVE_REQUEST = 'save_request'
    GET_REQUEST = 'get_request'
    UPDATE_REQUEST_STATUS = 'update_request_status'
    GET_PENDING_REQUESTS = 'get_pending_requests'
    SAVE_BATCH = 'save_batch'
    GET_BATCH = 'get_batch'
    SYNC_TO_FILE = 'sync_to_file'
    SYNC_TO_REDIS = 'sync_to_redis'
    VALIDATE_CONSISTENCY = 'validate_consistency'
    DELETE_PARENT_RUN = 'delete_parent_run'


class BackendType(Enum):
    """Backend types for metrics."""

    FILE = 'file'
    REDIS = 'redis'
    HYBRID = 'hybrid'


@dataclass
class OperationMetrics:
    """Metrics for a single operation type."""

    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.count == 0:
            return 0.0
        return self.total_latency_ms / self.count

    def record(self, success: bool, latency_ms: float) -> None:
        """Record an operation."""
        self.count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'count': self.count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': self.success_count / self.count if self.count > 0 else 0.0,
            'total_latency_ms': self.total_latency_ms,
            'avg_latency_ms': self.avg_latency_ms,
            'min_latency_ms': self.min_latency_ms if self.count > 0 else 0.0,
            'max_latency_ms': self.max_latency_ms,
        }


@dataclass
class RequestMetrics:
    """Metrics for request lifecycle."""

    total_requests: int = 0
    pending_requests: int = 0
    approved_requests: int = 0
    denied_requests: int = 0
    timeout_requests: int = 0
    cancelled_requests: int = 0

    def record_request(self, status: str) -> None:
        """Record a request status."""
        self.total_requests += 1
        if status == 'pending':
            self.pending_requests += 1
        elif status == 'approved':
            self.approved_requests += 1
        elif status == 'denied':
            self.denied_requests += 1
        elif status == 'timeout':
            self.timeout_requests += 1
        elif status == 'cancelled':
            self.cancelled_requests += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_requests': self.total_requests,
            'pending_requests': self.pending_requests,
            'approved_requests': self.approved_requests,
            'denied_requests': self.denied_requests,
            'timeout_requests': self.timeout_requests,
            'cancelled_requests': self.cancelled_requests,
        }


@dataclass
class ApprovalQueueMetrics:
    """Comprehensive metrics for approval queue operations."""

    backend_type: BackendType
    operation_metrics: dict[OperationType, OperationMetrics] = field(
        default_factory=lambda: defaultdict(lambda: OperationMetrics())
    )
    request_metrics: RequestMetrics = field(default_factory=RequestMetrics)
    circuit_breaker_stats: Optional[dict[str, Any]] = None
    redis_available: bool = True
    sync_errors: int = 0
    start_time: float = field(default_factory=time.time)

    _lock: Lock = field(default_factory=Lock)

    def record_operation(
        self,
        operation: OperationType,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record an operation."""
        with self._lock:
            self.operation_metrics[operation].record(success, latency_ms)

    def record_request_status(self, status: str) -> None:
        """Record a request status."""
        with self._lock:
            self.request_metrics.record_request(status)

    def record_sync_error(self) -> None:
        """Record a sync error."""
        with self._lock:
            self.sync_errors += 1

    def update_circuit_breaker_stats(self, stats: Optional[dict[str, Any]]) -> None:
        """Update circuit breaker statistics."""
        with self._lock:
            self.circuit_breaker_stats = stats

    def update_redis_availability(self, available: bool) -> None:
        """Update Redis availability status."""
        with self._lock:
            self.redis_available = available

    def get_operation_metrics(self, operation: OperationType) -> OperationMetrics:
        """Get metrics for a specific operation."""
        with self._lock:
            return self.operation_metrics[operation]

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            uptime_seconds = time.time() - self.start_time
            return {
                'backend_type': self.backend_type.value
                if self.backend_type
                else 'unknown',
                'uptime_seconds': uptime_seconds,
                'operation_metrics': {
                    op.value: metrics.to_dict()
                    for op, metrics in self.operation_metrics.items()
                },
                'request_metrics': self.request_metrics.to_dict(),
                'circuit_breaker_stats': self.circuit_breaker_stats,
                'redis_available': self.redis_available,
                'sync_errors': self.sync_errors,
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.operation_metrics = defaultdict(lambda: OperationMetrics())
            self.request_metrics = RequestMetrics()
            self.sync_errors = 0
            self.start_time = time.time()


class MetricsCollector:
    """Global metrics collector for approval queue operations."""

    _instance: Optional[MetricsCollector] = None
    _lock: Lock = Lock()

    def __new__(cls) -> MetricsCollector:
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize metrics collector."""
        if not hasattr(self, '_initialized'):
            self._metrics: dict[str, ApprovalQueueMetrics] = {}
            self._lock = Lock()
            self._initialized = True

    def get_or_create_metrics(
        self,
        backend_type: BackendType,
        parent_run_id: Optional[str] = None,
    ) -> ApprovalQueueMetrics:
        """Get or create metrics for a backend."""
        key = f'{backend_type.value}:{parent_run_id or "global"}'
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = ApprovalQueueMetrics(backend_type=backend_type)
            return self._metrics[key]

    def get_metrics(
        self,
        backend_type: Optional[BackendType] = None,
        parent_run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get metrics for a specific backend or all metrics."""
        with self._lock:
            if backend_type is None and parent_run_id is None:
                return {k: v.get_all_metrics() for k, v in self._metrics.items()}
            elif backend_type is not None:
                key = f'{backend_type.value}:{parent_run_id or "global"}'
                if key in self._metrics:
                    return self._metrics[key].get_all_metrics()
            return {}

    def reset_metrics(
        self,
        backend_type: Optional[BackendType] = None,
        parent_run_id: Optional[str] = None,
    ) -> None:
        """Reset metrics for a specific backend or all metrics."""
        with self._lock:
            if backend_type is None and parent_run_id is None:
                for metrics in self._metrics.values():
                    metrics.reset()
            elif backend_type is not None:
                key = f'{backend_type.value}:{parent_run_id or "global"}'
                if key in self._metrics:
                    self._metrics[key].reset()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return MetricsCollector()


class MetricsContext:
    """Context manager for timing operations."""

    def __init__(
        self,
        metrics: ApprovalQueueMetrics,
        operation: OperationType,
    ) -> None:
        """Initialize metrics context."""
        self._metrics = metrics
        self._operation = operation
        self._start_time: Optional[float] = None
        self._success = False

    def __enter__(self) -> MetricsContext:
        """Enter context and start timing."""
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Exit context and record metrics."""
        if self._start_time is None:
            return
        latency_ms = (time.time() - self._start_time) * 1000
        success = exc_type is None
        self._metrics.record_operation(self._operation, success, latency_ms)
        self._success = success

    def set_success(self, success: bool) -> None:
        """Manually set success status."""
        self._success = success
