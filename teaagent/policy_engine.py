"""Policy engine for collaboration rules and team operations.

This module provides the foundation for defining, storing, and evaluating
policies for collaborative agent workflows, including role-based access
control, consensus validation, and policy-based routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


class PolicyEffect(str, Enum):
    """Effect of a policy evaluation."""

    ALLOW = 'allow'
    DENY = 'deny'


class PolicyType(str, Enum):
    """Type of policy."""

    RBAC = 'rbac'  # Role-based access control
    CONSENSUS = 'consensus'  # Multi-agent consensus
    ROUTING = 'routing'  # Policy-based routing
    BUDGET = 'budget'  # Budget and cost control
    APPROVAL = 'approval'  # Approval workflow


class PolicyPrecedence(str, Enum):
    """Precedence levels for conflict resolution.

    Higher precedence policies override lower precedence policies.
    """

    CRITICAL = 'critical'  # Highest precedence (security, safety)
    HIGH = 'high'  # High precedence (cost, compliance)
    MEDIUM = 'medium'  # Medium precedence (operational)
    LOW = 'low'  # Lowest precedence (optimization, convenience)


@dataclass
class PolicyCondition:
    """Condition for policy evaluation.

    Conditions are evaluated against action context to determine
    if a policy applies.
    """

    field: str  # Field to check (e.g., 'action', 'role', 'tenant')
    operator: str  # Operator (e.g., 'equals', 'contains', 'in')
    value: Any  # Expected value

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate the condition against the context.

        Args:
            context: Action context to evaluate against.

        Returns:
            True if condition matches, False otherwise.
        """
        actual_value = context.get(self.field)

        if self.operator == 'equals':
            return actual_value == self.value
        elif self.operator == 'not_equals':
            return actual_value != self.value
        elif self.operator == 'contains':
            return self.value in str(actual_value) if actual_value else False
        elif self.operator == 'in':
            return (
                actual_value in self.value
                if isinstance(self.value, (list, set))
                else False
            )
        elif self.operator == 'not_in':
            return (
                actual_value not in self.value
                if isinstance(self.value, (list, set))
                else True
            )
        else:
            # Unknown operator, default to False
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'field': self.field,
            'operator': self.operator,
            'value': self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PolicyCondition':
        """Create from dictionary."""
        return cls(
            field=data['field'],
            operator=data['operator'],
            value=data['value'],
        )


@dataclass
class Policy:
    """A policy rule for collaborative agent workflows.

    Policies define conditions under which actions are allowed or denied,
    with support for role-based access control, consensus requirements,
    and routing rules.
    """

    policy_id: str
    policy_type: PolicyType
    effect: PolicyEffect
    conditions: list[PolicyCondition] = field(default_factory=list)
    precedence: PolicyPrecedence = PolicyPrecedence.MEDIUM
    description: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def evaluate(self, context: dict[str, Any]) -> Optional[PolicyEffect]:
        """Evaluate the policy against the given context.

        Args:
            context: Action context to evaluate against.

        Returns:
            PolicyEffect if policy applies, None if conditions don't match.
        """
        if not self.enabled:
            return None

        # All conditions must match for policy to apply
        for condition in self.conditions:
            if not condition.evaluate(context):
                return None

        return self.effect

    def applies_to(self, context: dict[str, Any]) -> bool:
        """Check if policy applies to the given context.

        Args:
            context: Action context to check.

        Returns:
            True if policy conditions match, False otherwise.
        """
        return self.evaluate(context) is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'policy_id': self.policy_id,
            'policy_type': self.policy_type.value,
            'effect': self.effect.value,
            'conditions': [c.to_dict() for c in self.conditions],
            'precedence': self.precedence.value,
            'description': self.description,
            'metadata': self.metadata,
            'enabled': self.enabled,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Policy':
        """Create from dictionary."""
        return cls(
            policy_id=data['policy_id'],
            policy_type=PolicyType(data['policy_type']),
            effect=PolicyEffect(data['effect']),
            conditions=[
                PolicyCondition.from_dict(c) for c in data.get('conditions', [])
            ],
            precedence=PolicyPrecedence(data.get('precedence', 'medium')),
            description=data.get('description', ''),
            metadata=data.get('metadata', {}),
            enabled=data.get('enabled', True),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
        )


class PolicyStore:
    """Storage for policies.

    Provides persistent storage and retrieval of policies with support
    for tenant-specific policies and policy versioning.
    """

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the policy store.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

        if tenant_id == 'default':
            self.store_dir = self.root / '.teaagent' / 'policies'
        else:
            self.store_dir = (
                self.root / '.teaagent' / 'tenants' / tenant_id / 'policies'
            )

        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _policy_path(self, policy_id: str) -> Path:
        """Get the file path for a policy."""
        return self.store_dir / f'{policy_id}.json'

    def save(self, policy: Policy) -> None:
        """Save a policy to storage.

        Args:
            policy: Policy to save.
        """
        import time

        from teaagent.storage import atomic_write_text

        path = self._policy_path(policy.policy_id)

        # Update timestamps
        if path.exists():
            # Preserve created_at if updating existing policy
            existing = self.load(policy.policy_id)
            if existing:
                policy.created_at = existing.created_at
        else:
            # Set created_at for new policy
            if policy.created_at is None:
                policy.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        policy.updated_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Write to file
        atomic_write_text(path, json.dumps(policy.to_dict(), indent=2))

    def load(self, policy_id: str) -> Optional[Policy]:
        """Load a policy from storage.

        Args:
            policy_id: Policy ID to load.

        Returns:
            Policy if found, None otherwise.
        """
        path = self._policy_path(policy_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return Policy.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete(self, policy_id: str) -> bool:
        """Delete a policy from storage.

        Args:
            policy_id: Policy ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._policy_path(policy_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list(
        self, *, policy_type: Optional[PolicyType] = None, enabled_only: bool = False
    ) -> list[Policy]:
        """List all policies.

        Args:
            policy_type: Optional filter by policy type.
            enabled_only: If True, only return enabled policies.

        Returns:
            List of policies.
        """
        policies = []
        for path in self.store_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                policy = Policy.from_dict(data)

                # Apply filters
                if policy_type and policy.policy_type != policy_type:
                    continue
                if enabled_only and not policy.enabled:
                    continue

                policies.append(policy)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return policies

    def count(
        self, *, policy_type: Optional[PolicyType] = None, enabled_only: bool = False
    ) -> int:
        """Count policies.

        Args:
            policy_type: Optional filter by policy type.
            enabled_only: If True, only count enabled policies.

        Returns:
            Number of policies.
        """
        return len(self.list(policy_type=policy_type, enabled_only=enabled_only))


class PolicyEngine:
    """Engine for evaluating policies against actions.

    The policy engine evaluates policies in precedence order and returns
    the final allow/deny decision based on the highest-precedence matching
    policy.
    """

    def __init__(self, store: PolicyStore) -> None:
        """Initialize the policy engine.

        Args:
            store: Policy store to use for policy retrieval.
        """
        self.store = store

    def evaluate(
        self,
        context: dict[str, Any],
        *,
        policy_type: Optional[PolicyType] = None,
    ) -> PolicyEffect:
        """Evaluate policies against the given context.

        Args:
            context: Action context to evaluate.
            policy_type: Optional filter by policy type.

        Returns:
            PolicyEffect (ALLOW or DENY).
        """
        # Get all applicable policies
        policies = self.store.list(policy_type=policy_type, enabled_only=True)

        # Sort by precedence (highest first)
        precedence_order = {
            PolicyPrecedence.CRITICAL: 0,
            PolicyPrecedence.HIGH: 1,
            PolicyPrecedence.MEDIUM: 2,
            PolicyPrecedence.LOW: 3,
        }
        policies.sort(key=lambda p: precedence_order.get(p.precedence, 99))

        # Evaluate policies in precedence order
        for policy in policies:
            effect = policy.evaluate(context)
            if effect is not None:
                # Policy applies, return its effect
                return effect

        # No policies matched, default to ALLOW
        return PolicyEffect.ALLOW

    def evaluate_with_explanation(
        self,
        context: dict[str, Any],
        *,
        policy_type: Optional[PolicyType] = None,
    ) -> tuple[PolicyEffect, list[dict[str, Any]]]:
        """Evaluate policies with detailed explanation.

        Args:
            context: Action context to evaluate.
            policy_type: Optional filter by policy type.

        Returns:
            Tuple of (PolicyEffect, list of evaluation details).
        """
        policies = self.store.list(policy_type=policy_type, enabled_only=True)

        precedence_order = {
            PolicyPrecedence.CRITICAL: 0,
            PolicyPrecedence.HIGH: 1,
            PolicyPrecedence.MEDIUM: 2,
            PolicyPrecedence.LOW: 3,
        }
        policies.sort(key=lambda p: precedence_order.get(p.precedence, 99))

        details = []
        final_effect = PolicyEffect.ALLOW

        for policy in policies:
            effect = policy.evaluate(context)
            detail = {
                'policy_id': policy.policy_id,
                'policy_type': policy.policy_type.value,
                'precedence': policy.precedence.value,
                'applies': effect is not None,
                'effect': effect.value if effect else None,
                'description': policy.description,
            }
            details.append(detail)

            if effect is not None:
                final_effect = effect
                # Stop at first matching policy (highest precedence)
                break

        return final_effect, details

    def check_permission(
        self,
        action: str,
        role: str,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if a role has permission for an action.

        Args:
            action: Action to check.
            role: Role to check.
            context: Additional context for evaluation.

        Returns:
            Tuple of (allowed, reason).
        """
        evaluation_context = {
            'action': action,
            'role': role,
            **context,
        }

        effect, details = self.evaluate_with_explanation(
            evaluation_context,
            policy_type=PolicyType.RBAC,
        )

        if effect == PolicyEffect.ALLOW:
            return True, 'Permission granted by policy'
        else:
            # Find the denying policy
            for detail in details:
                if detail['applies'] and detail['effect'] == 'deny':
                    return False, f'Permission denied by policy: {detail["policy_id"]}'

            return False, 'Permission denied by default policy'

    def create_policy(
        self,
        policy_type: PolicyType,
        effect: PolicyEffect,
        conditions: list[dict[str, Any]],
        *,
        precedence: PolicyPrecedence = PolicyPrecedence.MEDIUM,
        description: str = '',
        metadata: Optional[dict[str, Any]] = None,
    ) -> Policy:
        """Create a new policy.

        Args:
            policy_type: Type of policy.
            effect: Effect of the policy.
            conditions: List of condition dictionaries.
            precedence: Precedence level.
            description: Policy description.
            metadata: Additional metadata.

        Returns:
            Created policy.
        """
        policy_id = str(uuid4())

        condition_objects = [
            PolicyCondition(
                field=c['field'],
                operator=c['operator'],
                value=c['value'],
            )
            for c in conditions
        ]

        policy = Policy(
            policy_id=policy_id,
            policy_type=policy_type,
            effect=effect,
            conditions=condition_objects,
            precedence=precedence,
            description=description,
            metadata=metadata or {},
        )

        self.store.save(policy)
        return policy
