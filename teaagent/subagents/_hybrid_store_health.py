"""Health, lifecycle, and maintenance mixin for hybrid approval queue store."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import request_from_dict

logger = logging.getLogger(__name__)


class HybridStoreHealthMixin:
    """Mixin providing health operations for HybridApprovalQueueStore."""

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
            validation['error'] = str(e)

        return validation

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
