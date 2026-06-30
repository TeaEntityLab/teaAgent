"""Multi-agent consensus validation system.

experimental — unwired

This module provides consensus validation for collaborative agent workflows,
including consensus rules, vote tracking, and consensus decision logic.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.governance.policy_engine import (
    PolicyEffect,
    PolicyEngine,
    PolicyStore,
    PolicyType,
)


class ConsensusStatus(str, Enum):
    """Status of a consensus request."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class ConsensusRuleType(str, Enum):
    """Type of consensus rule."""

    N_OF_M = 'n_of_m'  # N out of M required
    UNANIMOUS = 'unanimous'  # All must agree
    MAJORITY = 'majority'  # Simple majority
    SUPERMAJORITY = 'supermajority'  # 2/3 majority
    ROLE_BASED = 'role_based'  # Specific roles must approve


@dataclass
class ConsensusRule:
    """A consensus rule for collaborative decisions."""

    rule_id: str
    rule_type: ConsensusRuleType
    required_approvals: int  # For N_OF_M, this is N
    total_voters: int  # For N_OF_M, this is M
    required_roles: set[str] = field(default_factory=set)
    timeout_seconds: int = 3600  # Default 1 hour
    description: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def check_consensus(
        self,
        votes: dict[str, bool],
        voter_roles: Optional[Mapping[str, str]] = None,
    ) -> ConsensusStatus:
        """Check if consensus is reached based on votes.

        Args:
            votes: Dictionary mapping voter IDs to their vote (True=approve, False=reject).
            voter_roles: Optional mapping of voter ID -> role name, consulted only
                for ROLE_BASED rules. When a voter is absent from this mapping (or
                the mapping is omitted entirely) the voter ID is treated as its own
                role, which is the documented default contract.

        Returns:
            Consensus status.
        """
        if not votes:
            return ConsensusStatus.PENDING

        approve_count = sum(1 for vote in votes.values() if vote)
        reject_count = sum(1 for vote in votes.values() if not vote)
        total_votes = len(votes)

        if self.rule_type == ConsensusRuleType.N_OF_M:
            if approve_count >= self.required_approvals:
                return ConsensusStatus.APPROVED
            elif reject_count > (self.total_voters - self.required_approvals):
                return ConsensusStatus.REJECTED
            else:
                return ConsensusStatus.PENDING

        elif self.rule_type == ConsensusRuleType.UNANIMOUS:
            if approve_count == total_votes:
                return ConsensusStatus.APPROVED
            elif reject_count > 0:
                return ConsensusStatus.REJECTED
            else:
                return ConsensusStatus.PENDING

        elif self.rule_type == ConsensusRuleType.MAJORITY:
            if approve_count > total_votes / 2:
                return ConsensusStatus.APPROVED
            elif reject_count > total_votes / 2:
                return ConsensusStatus.REJECTED
            else:
                return ConsensusStatus.PENDING

        elif self.rule_type == ConsensusRuleType.SUPERMAJORITY:
            if approve_count >= (2 * total_votes) / 3:
                return ConsensusStatus.APPROVED
            elif reject_count > total_votes / 3:
                return ConsensusStatus.REJECTED
            else:
                return ConsensusStatus.PENDING

        elif self.rule_type == ConsensusRuleType.ROLE_BASED:
            # Resolve each approving voter to the role it holds. When an explicit
            # voter->role mapping is supplied the role is looked up; otherwise the
            # voter_id is treated as its own role. The fallback is the documented
            # default contract for callers that encode the role directly in the
            # voter_id (e.g. "security", "architecture").
            role_map = voter_roles or {}
            approved_roles: set[str] = set()
            for voter_id, approved in votes.items():
                if approved:
                    approved_roles.add(role_map.get(voter_id, voter_id))

            if self.required_roles.issubset(approved_roles):
                return ConsensusStatus.APPROVED
            else:
                return ConsensusStatus.PENDING

        return ConsensusStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'rule_id': self.rule_id,
            'rule_type': self.rule_type.value,
            'required_approvals': self.required_approvals,
            'total_voters': self.total_voters,
            'required_roles': list(self.required_roles),
            'timeout_seconds': self.timeout_seconds,
            'description': self.description,
            'metadata': self.metadata,
            'enabled': self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ConsensusRule':
        """Create from dictionary."""
        return cls(
            rule_id=data['rule_id'],
            rule_type=ConsensusRuleType(data['rule_type']),
            required_approvals=data['required_approvals'],
            total_voters=data['total_voters'],
            required_roles=set(data.get('required_roles', [])),
            timeout_seconds=data.get('timeout_seconds', 3600),
            description=data.get('description', ''),
            metadata=data.get('metadata', {}),
            enabled=data.get('enabled', True),
        )


@dataclass
class ConsensusRequest:
    """A request for consensus on an action."""

    request_id: str
    rule_id: str
    action: str
    context: dict[str, Any]
    requested_by: str
    status: ConsensusStatus = ConsensusStatus.PENDING
    votes: dict[str, bool] = field(default_factory=dict)
    voter_roles: dict[str, str] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_vote(
        self, voter_id: str, approve: bool, role: Optional[str] = None
    ) -> None:
        """Add a vote to the consensus request.

        Args:
            voter_id: ID of the voter.
            approve: True for approve, False for reject.
            role: Optional role held by the voter, used for ROLE_BASED rules.
        """
        self.votes[voter_id] = approve
        if role is not None:
            self.voter_roles[voter_id] = role

    def is_expired(self) -> bool:
        """Check if the request has expired.

        Returns:
            True if expired, False otherwise.
        """
        if self.expires_at is None:
            return False

        from datetime import datetime, timezone

        try:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return now >= expiry
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'request_id': self.request_id,
            'rule_id': self.rule_id,
            'action': self.action,
            'context': self.context,
            'requested_by': self.requested_by,
            'status': self.status.value,
            'votes': self.votes,
            'voter_roles': self.voter_roles,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'expires_at': self.expires_at,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ConsensusRequest':
        """Create from dictionary."""
        return cls(
            request_id=data['request_id'],
            rule_id=data['rule_id'],
            action=data['action'],
            context=data['context'],
            requested_by=data['requested_by'],
            status=ConsensusStatus(data.get('status', 'pending')),
            votes=data.get('votes', {}),
            voter_roles=data.get('voter_roles', {}),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            expires_at=data.get('expires_at'),
            metadata=data.get('metadata', {}),
        )


class ConsensusStore:
    """Storage for consensus rules and requests."""

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the consensus store.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id

        if tenant_id == 'default':
            self.rules_dir = self.root / '.teaagent' / 'consensus-rules'
            self.requests_dir = self.root / '.teaagent' / 'consensus-requests'
        else:
            self.rules_dir = (
                self.root / '.teaagent' / 'tenants' / tenant_id / 'consensus-rules'
            )
            self.requests_dir = (
                self.root / '.teaagent' / 'tenants' / tenant_id / 'consensus-requests'
            )

        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.requests_dir.mkdir(parents=True, exist_ok=True)

    def _rule_path(self, rule_id: str) -> Path:
        """Get the file path for a consensus rule."""
        return self.rules_dir / f'{rule_id}.json'

    def _request_path(self, request_id: str) -> Path:
        """Get the file path for a consensus request."""
        return self.requests_dir / f'{request_id}.json'

    def save_rule(self, rule: ConsensusRule) -> None:
        """Save a consensus rule to storage.

        Args:
            rule: Rule to save.
        """
        from teaagent.storage import atomic_write_text

        path = self._rule_path(rule.rule_id)
        atomic_write_text(path, json.dumps(rule.to_dict(), indent=2))

    def load_rule(self, rule_id: str) -> Optional[ConsensusRule]:
        """Load a consensus rule from storage.

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
            return ConsensusRule.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a consensus rule from storage.

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

    def list_rules(self, *, enabled_only: bool = False) -> list[ConsensusRule]:
        """List all consensus rules.

        Args:
            enabled_only: If True, only return enabled rules.

        Returns:
            List of rules.
        """
        rules = []
        for path in self.rules_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                rule = ConsensusRule.from_dict(data)
                if enabled_only and not rule.enabled:
                    continue
                rules.append(rule)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return rules

    def save_request(self, request: ConsensusRequest) -> None:
        """Save a consensus request to storage.

        Args:
            request: Request to save.
        """
        import time

        from teaagent.storage import atomic_write_text

        path = self._request_path(request.request_id)

        if request.created_at is None:
            request.created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        request.updated_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        atomic_write_text(path, json.dumps(request.to_dict(), indent=2))

    def load_request(self, request_id: str) -> Optional[ConsensusRequest]:
        """Load a consensus request from storage.

        Args:
            request_id: Request ID to load.

        Returns:
            Request if found, None otherwise.
        """
        path = self._request_path(request_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return ConsensusRequest.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete_request(self, request_id: str) -> bool:
        """Delete a consensus request from storage.

        Args:
            request_id: Request ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._request_path(request_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_requests(
        self,
        *,
        status: Optional[ConsensusStatus] = None,
        rule_id: Optional[str] = None,
    ) -> list[ConsensusRequest]:
        """List consensus requests.

        Args:
            status: Optional filter by status.
            rule_id: Optional filter by rule ID.

        Returns:
            List of requests.
        """
        requests = []
        for path in self.requests_dir.glob('*.json'):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                request = ConsensusRequest.from_dict(data)

                if status and request.status != status:
                    continue
                if rule_id and request.rule_id != rule_id:
                    continue

                requests.append(request)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return requests


class ConsensusValidator:
    """Validator for multi-agent consensus.

    Manages consensus rules, requests, and voting for collaborative decisions.
    """

    def __init__(self, root: str | Path, *, tenant_id: str = 'default') -> None:
        """Initialize the consensus validator.

        Args:
            root: Workspace root directory.
            tenant_id: Tenant ID for multi-tenant scenarios.
        """
        self.root = Path(root).resolve()
        self.tenant_id = tenant_id
        self.store = ConsensusStore(self.root, tenant_id=tenant_id)
        self.policy_engine = PolicyEngine(PolicyStore(self.root, tenant_id=tenant_id))

    def create_rule(
        self,
        rule_type: ConsensusRuleType,
        required_approvals: int,
        total_voters: int,
        *,
        required_roles: Optional[set[str]] = None,
        timeout_seconds: int = 3600,
        description: str = '',
        metadata: Optional[dict[str, Any]] = None,
    ) -> ConsensusRule:
        """Create a new consensus rule.

        Args:
            rule_type: Type of consensus rule.
            required_approvals: Number of approvals required.
            total_voters: Total number of voters.
            required_roles: Required roles for role-based consensus.
            timeout_seconds: Timeout for consensus requests.
            description: Rule description.
            metadata: Additional metadata.

        Returns:
            Created rule.
        """
        rule_id = str(uuid4())
        rule = ConsensusRule(
            rule_id=rule_id,
            rule_type=rule_type,
            required_approvals=required_approvals,
            total_voters=total_voters,
            required_roles=required_roles or set(),
            timeout_seconds=timeout_seconds,
            description=description,
            metadata=metadata or {},
        )

        self.store.save_rule(rule)

        # Create corresponding policy for the rule
        self._create_rule_policy(rule)

        return rule

    def _create_rule_policy(self, rule: ConsensusRule) -> None:
        """Create a policy for a consensus rule.

        Args:
            rule: Rule to create policy for.
        """
        conditions = [
            {
                'field': 'consensus_rule',
                'operator': 'equals',
                'value': rule.rule_id,
            }
        ]

        self.policy_engine.create_policy(
            policy_type=PolicyType.CONSENSUS,
            effect=PolicyEffect.ALLOW,
            conditions=conditions,
            description=f'Consensus policy for rule: {rule.rule_id}',
            metadata={'rule_id': rule.rule_id},
        )

    def request_consensus(
        self,
        rule_id: str,
        action: str,
        context: dict[str, Any],
        requested_by: str,
    ) -> ConsensusRequest:
        """Request consensus for an action.

        Args:
            rule_id: Rule ID to use for consensus.
            action: Action requiring consensus.
            context: Additional context.
            requested_by: ID of the requester.

        Returns:
            Created consensus request.
        """
        rule = self.store.load_rule(rule_id)
        if not rule:
            raise ValueError(f'Rule not found: {rule_id}')

        request_id = str(uuid4())

        # Calculate expiration time
        from datetime import datetime, timedelta, timezone

        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=rule.timeout_seconds)
        ).isoformat()

        request = ConsensusRequest(
            request_id=request_id,
            rule_id=rule_id,
            action=action,
            context=context,
            requested_by=requested_by,
            expires_at=expires_at,
        )

        self.store.save_request(request)
        return request

    def cast_vote(
        self,
        request_id: str,
        voter_id: str,
        approve: bool,
        role: Optional[str] = None,
    ) -> ConsensusRequest:
        """Cast a vote on a consensus request.

        Args:
            request_id: Request ID to vote on.
            voter_id: ID of the voter.
            approve: True for approve, False for reject.
            role: Optional role held by the voter, recorded for ROLE_BASED rules.

        Returns:
            Updated consensus request.
        """
        request = self.store.load_request(request_id)
        if not request:
            raise ValueError(f'Request not found: {request_id}')

        if request.status != ConsensusStatus.PENDING:
            raise ValueError(f'Request is not pending: {request.status}')

        if request.is_expired():
            request.status = ConsensusStatus.EXPIRED
            self.store.save_request(request)
            return request

        request.add_vote(voter_id, approve, role=role)

        # Check if consensus is reached
        rule = self.store.load_rule(request.rule_id)
        if rule:
            consensus_status = rule.check_consensus(
                request.votes, request.voter_roles or None
            )
            request.status = consensus_status

        self.store.save_request(request)
        return request

    def get_consensus_status(self, request_id: str) -> Optional[ConsensusStatus]:
        """Get the current status of a consensus request.

        Args:
            request_id: Request ID to check.

        Returns:
            Consensus status, or None if request not found.
        """
        request = self.store.load_request(request_id)
        if not request:
            return None

        # Check if expired
        if request.is_expired():
            request.status = ConsensusStatus.EXPIRED
            self.store.save_request(request)

        return request.status

    def create_default_rules(self) -> None:
        """Create default consensus rules.

        Creates standard rules: 2-of-3, unanimous, majority.
        """
        # 2-of-3 rule for production deployments
        self.create_rule(
            ConsensusRuleType.N_OF_M,
            required_approvals=2,
            total_voters=3,
            description='2-of-3 consensus for production deployments',
            metadata={'action_type': 'deploy', 'environment': 'production'},
        )

        # Unanimous rule for destructive actions
        self.create_rule(
            ConsensusRuleType.UNANIMOUS,
            required_approvals=0,  # Not used for unanimous
            total_voters=0,  # Not used for unanimous
            description='Unanimous consensus for destructive actions',
            metadata={'action_type': 'destructive'},
        )

        # Majority rule for operational decisions
        self.create_rule(
            ConsensusRuleType.MAJORITY,
            required_approvals=0,  # Not used for majority
            total_voters=0,  # Not used for majority
            description='Majority consensus for operational decisions',
            metadata={'action_type': 'operational'},
        )
