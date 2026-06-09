"""Policy-based routing for collaborative agent workflows.

This module provides routing rules and decision logic for routing actions
based on policies, including role-aware routing and policy-based dispatch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .policy_engine import PolicyEffect, PolicyEngine, PolicyStore, PolicyType
from .rbac import RBACSystem


class RoutingDecision(str, Enum):
    """Routing decision for an action."""

    ALLOW = 'allow'  # Action allowed, proceed normally
    DENY = 'deny'  # Action denied, block execution
    REQUIRE_APPROVAL = 'require_approval'  # Action requires approval
    REQUIRE_CONSENSUS = 'require_consensus'  # Action requires consensus
    ROUTE_TO_SPECIALIST = 'route_to_specialist'  # Route to specialist agent
    DEFER = 'defer'  # Defer action for later


class RoutingTarget(str, Enum):
    """Target for routing."""

    DEFAULT = 'default'  # Default agent
    SPECIALIST = 'specialist'  # Specialist agent
    HUMAN = 'human'  # Human operator
    QUEUE = 'queue'  # Action queue
    BLOCK = 'block'  # Block execution


@dataclass
class RoutingRule:
    """A routing rule for action dispatch."""

    rule_id: str
    action_pattern: str  # Pattern to match actions (e.g., 'deploy:*')
    decision: RoutingDecision
    target: RoutingTarget = RoutingTarget.DEFAULT
    required_roles: set[str] = field(default_factory=set)
    required_consensus_rule: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0  # Higher priority rules evaluated first

    def matches_action(self, action: str) -> bool:
        """Check if the rule matches an action.

        Args:
            action: Action to check.

        Returns:
            True if rule matches, False otherwise.
        """
        # Simple pattern matching (supports wildcards)
        if '*' in self.action_pattern:
            pattern = self.action_pattern.replace('*', '.*')
            import re

            return re.match(pattern, action) is not None
        else:
            return action == self.action_pattern

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'rule_id': self.rule_id,
            'action_pattern': self.action_pattern,
            'decision': self.decision.value,
            'target': self.target.value,
            'required_roles': list(self.required_roles),
            'required_consensus_rule': self.required_consensus_rule,
            'metadata': self.metadata,
            'enabled': self.enabled,
            'priority': self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'RoutingRule':
        """Create from dictionary."""
        return cls(
            rule_id=data['rule_id'],
            action_pattern=data['action_pattern'],
            decision=RoutingDecision(data['decision']),
            target=RoutingTarget(data.get('target', 'default')),
            required_roles=set(data.get('required_roles', [])),
            required_consensus_rule=data.get('required_consensus_rule'),
            metadata=data.get('metadata', {}),
            enabled=data.get('enabled', True),
            priority=data.get('priority', 0),
        )


class RoutingStore:
    """Storage for routing rules."""

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the routing store.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

        if tenant_id == 'default':
            self.rules_dir = self.root / '.teaagent' / 'routing-rules'
        else:
            self.rules_dir = (
                self.root / '.teaagent' / 'tenants' / tenant_id / 'routing-rules'
            )

        self.rules_dir.mkdir(parents=True, exist_ok=True)

    def _rule_path(self, rule_id: str) -> Path:
        """Get the file path for a routing rule."""
        return self.rules_dir / f'{rule_id}.json'

    def save_rule(self, rule: RoutingRule) -> None:
        """Save a routing rule to storage.

        Args:
            rule: Rule to save.
        """
        from teaagent.storage import atomic_write_text

        path = self._rule_path(rule.rule_id)
        atomic_write_text(path, json.dumps(rule.to_dict(), indent=2))

    def load_rule(self, rule_id: str) -> Optional[RoutingRule]:
        """Load a routing rule from storage.

        Args:
            rule_id: Rule ID to load.

        Returns:
            Rule if found, None otherwise.
        """
        path = self._rule_path(rule_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return RoutingRule.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a routing rule from storage.

        Args:
            rule_id: Rule ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._rule_path(rule_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_rules(self, *, enabled_only: bool = False) -> list[RoutingRule]:
        """List all routing rules.

        Args:
            enabled_only: If True, only return enabled rules.

        Returns:
            List of rules.
        """
        rules = []
        for path in self.rules_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                rule = RoutingRule.from_dict(data)
                if enabled_only and not rule.enabled:
                    continue
                rules.append(rule)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return rules


class PolicyRouter:
    """Router for policy-based action dispatch.

    Evaluates routing rules and policies to determine how actions should be routed.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        tenant_id: str = 'default',
    ) -> None:
        """Initialize the policy router.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self.routing_store = RoutingStore(self.root, tenant_id=tenant_id)
        self.policy_store = PolicyStore(self.root, tenant_id=tenant_id)
        self.policy_engine = PolicyEngine(self.policy_store)
        self.rbac_system = RBACSystem(self.root, tenant_id=tenant_id)

    def create_routing_rule(
        self,
        action_pattern: str,
        decision: RoutingDecision,
        *,
        target: RoutingTarget = RoutingTarget.DEFAULT,
        required_roles: Optional[set[str]] = None,
        required_consensus_rule: Optional[str] = None,
        priority: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RoutingRule:
        """Create a new routing rule.

        Args:
            action_pattern: Pattern to match actions.
            decision: Routing decision.
            target: Routing target.
            required_roles: Required roles for this rule.
            required_consensus_rule: Required consensus rule ID.
            priority: Rule priority (higher evaluated first).
            metadata: Additional metadata.

        Returns:
            Created routing rule.
        """
        rule_id = str(uuid4())
        rule = RoutingRule(
            rule_id=rule_id,
            action_pattern=action_pattern,
            decision=decision,
            target=target,
            required_roles=required_roles or set(),
            required_consensus_rule=required_consensus_rule,
            priority=priority,
            metadata=metadata or {},
        )

        self.routing_store.save_rule(rule)

        # Create corresponding policy for the routing rule
        self._create_routing_policy(rule)

        return rule

    def _create_routing_policy(self, rule: RoutingRule) -> None:
        """Create a policy for a routing rule.

        Args:
            rule: Rule to create policy for.
        """
        conditions = [
            {
                'field': 'action',
                'operator': 'contains',
                'value': rule.action_pattern.replace('*', ''),
            }
        ]

        self.policy_engine.create_policy(
            policy_type=PolicyType.ROUTING,
            effect=PolicyEffect.ALLOW,
            conditions=conditions,
            description=f'Routing policy for pattern: {rule.action_pattern}',
            metadata={'rule_id': rule.rule_id},
        )

    def route_action(
        self,
        action: str,
        assignee: str,
        context: dict[str, Any],
    ) -> tuple[RoutingDecision, RoutingTarget, str]:
        """Route an action based on policies and rules.

        Args:
            action: Action to route.
            assignee: ID of the assignee (user or agent).
            context: Additional context for routing.

        Returns:
            Tuple of (decision, target, reason).
        """
        # Get all routing rules, sorted by priority (highest first)
        rules = self.routing_store.list_rules(enabled_only=True)
        rules.sort(key=lambda r: r.priority, reverse=True)

        # Find the first matching rule
        for rule in rules:
            if rule.matches_action(action):
                # Check if assignee has required roles
                if rule.required_roles:
                    assignee_roles = {
                        role.name
                        for role in self.rbac_system.get_roles_for_assignee(assignee)
                    }
                    if not rule.required_roles.issubset(assignee_roles):
                        return (
                            RoutingDecision.DENY,
                            RoutingTarget.BLOCK,
                            f'Assignee lacks required roles: {rule.required_roles}',
                        )

                # Check if consensus is required
                if (
                    rule.decision == RoutingDecision.REQUIRE_CONSENSUS
                    and rule.required_consensus_rule
                ):
                    return (
                        RoutingDecision.REQUIRE_CONSENSUS,
                        rule.target,
                        f'Consensus required by rule: {rule.required_consensus_rule}',
                    )

                return (
                    rule.decision,
                    rule.target,
                    f'Routed by rule: {rule.rule_id}',
                )

        # No matching rule, use policy engine for final decision
        policy_context = {
            'action': action,
            'assignee': assignee,
            **context,
        }

        effect = self.policy_engine.evaluate(
            policy_context, policy_type=PolicyType.ROUTING
        )

        if effect == PolicyEffect.ALLOW:
            return (
                RoutingDecision.ALLOW,
                RoutingTarget.DEFAULT,
                'Allowed by policy engine',
            )
        else:
            return (
                RoutingDecision.DENY,
                RoutingTarget.BLOCK,
                'Denied by policy engine',
            )

    def check_routing_permission(
        self,
        action: str,
        assignee: str,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if an action is allowed to be routed.

        Args:
            action: Action to check.
            assignee: ID of the assignee.
            context: Additional context.

        Returns:
            Tuple of (allowed, reason).
        """
        decision, target, reason = self.route_action(action, assignee, context)

        if decision == RoutingDecision.DENY:
            return False, reason
        elif decision == RoutingDecision.REQUIRE_APPROVAL:
            return False, f'Approval required: {reason}'
        elif decision == RoutingDecision.REQUIRE_CONSENSUS:
            return False, f'Consensus required: {reason}'
        else:
            return True, reason

    def create_default_routing_rules(self) -> None:
        """Create default routing rules.

        Creates standard rules for common action patterns.
        """
        # Destructive actions require consensus
        self.create_routing_rule(
            'delete:*',
            RoutingDecision.REQUIRE_CONSENSUS,
            required_consensus_rule='unanimous',
            priority=100,
            metadata={'action_type': 'destructive'},
        )

        # Production deployments require approval
        self.create_routing_rule(
            'deploy:production',
            RoutingDecision.REQUIRE_APPROVAL,
            target=RoutingTarget.HUMAN,
            priority=90,
            metadata={'action_type': 'deploy', 'environment': 'production'},
        )

        # Development deployments allowed for developers
        self.create_routing_rule(
            'deploy:development',
            RoutingDecision.ALLOW,
            required_roles={'developer', 'admin'},
            priority=80,
            metadata={'action_type': 'deploy', 'environment': 'development'},
        )

        # Read operations allowed for all
        self.create_routing_rule(
            'read:*',
            RoutingDecision.ALLOW,
            priority=10,
            metadata={'action_type': 'read'},
        )

        # Write operations require developer role
        self.create_routing_rule(
            'write:*',
            RoutingDecision.ALLOW,
            required_roles={'developer', 'admin'},
            priority=50,
            metadata={'action_type': 'write'},
        )
