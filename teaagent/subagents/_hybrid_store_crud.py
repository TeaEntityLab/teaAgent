"""CRUD operations mixin for hybrid approval queue store."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional, cast

from teaagent.subagents._approval_queue import (
    ApprovalBatch,
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_metrics import (
    MetricsContext,
    OperationType,
)
from teaagent.subagents._hybrid_store_base import HybridStoreBase

logger = logging.getLogger(__name__)


class HybridStoreCrudMixin(HybridStoreBase):
    """Mixin providing crud operations for HybridApprovalQueueStore."""

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
        results: dict[str, Any] = {
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
        results: dict[str, Any] = {
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
