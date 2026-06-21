"""Migration and state persistence mixin for hybrid approval queue store."""

from __future__ import annotations

import contextlib
import json
import logging
import time
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)
from teaagent.subagents._approval_queue_store import request_from_dict
from teaagent.subagents._hybrid_store_base import HybridStoreBase

logger = logging.getLogger(__name__)


class HybridStoreMigrationMixin(HybridStoreBase):
    """Mixin providing migration operations for HybridApprovalQueueStore."""

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

        checks: list[Any] = []

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
                redis_loaded = self._redis_store.get_request(
                    test_parent_run_id, test_request.request_id
                )
                checks.append(('Redis save operation', redis_loaded is not None))
            except Exception as e:
                checks.append(('Redis save operation', False, str(e)))

            try:
                redis_read = self._redis_store.get_request(
                    test_parent_run_id, test_request.request_id
                )
                checks.append(('Redis read operation', redis_read is not None))
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
            test_queue_path = self._file_store.queue_path(test_parent_run_id)
            if test_queue_path.exists():
                test_queue_path.unlink()
            if self._redis_store:
                self._redis_store.delete_parent_run(test_parent_run_id)
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

        checks: list[Any] = []

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

        checks: list[Any] = []

        # Get counts from both backends
        try:
            if source == 'file':
                source_count = len(self._file_store.get_all_requests())
            elif self._redis_store is not None:
                source_count = len(self._redis_store.get_all_requests())
            else:
                source_count = 0

            if destination == 'file':
                dest_count = len(self._file_store.get_all_requests())
            elif self._redis_store is not None:
                dest_count = len(self._redis_store.get_all_requests())
            else:
                dest_count = 0

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
                    pid: Optional[str] = request_dict.get('parent_run_id')
                    if pid and isinstance(pid, str):
                        if pid not in requests_by_parent:
                            requests_by_parent[pid] = []
                        requests_by_parent[pid].append(request_dict)

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
    ) -> dict[str, Any]:
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
                                    migrated_req: Optional[Any] = (
                                        self._redis_store.get_request(
                                            parent_run_id, request_id
                                        )
                                    )
                                    if migrated_req is not None:
                                        requests[request_id] = migrated_req.to_dict()
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
