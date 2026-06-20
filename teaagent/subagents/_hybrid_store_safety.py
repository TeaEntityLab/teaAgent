"""Security, audit, analytics mixin for hybrid approval queue store."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import zlib
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)

logger = logging.getLogger(__name__)


class HybridStoreSafetyMixin:
    """Mixin providing safety operations for HybridApprovalQueueStore."""

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

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics for this store."""
        self._metrics.update_circuit_breaker_stats(self.get_circuit_breaker_stats())
        self._metrics.update_redis_availability(self._redis_available)
        return self._metrics.get_all_metrics()

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
