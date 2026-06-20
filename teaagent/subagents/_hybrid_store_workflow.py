"""Workflow, SLA, import/export, and reporting mixin for hybrid approval queue store."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)

logger = logging.getLogger(__name__)


class HybridStoreWorkflowMixin:
    """Mixin providing workflow operations for HybridApprovalQueueStore."""

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
