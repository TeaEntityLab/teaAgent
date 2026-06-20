"""Policy, governance, and delegation mixin for hybrid approval queue store."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
    SubagentApprovalRequest,
)

logger = logging.getLogger(__name__)


class HybridStoreGovernanceMixin:
    """Mixin providing governance operations for HybridApprovalQueueStore."""

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
