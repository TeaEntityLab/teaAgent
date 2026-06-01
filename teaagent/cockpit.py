"""Operator cockpit state model for TUI and CLI surfaces.

This module provides CockpitState, a unified state model for the operator
cockpit that displays blocked approvals, harness health, budget status, and
recoverable state across all surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class HealthStatus(str, Enum):
    """Health status for harness and components."""

    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


class BudgetStatus(str, Enum):
    """Budget status for cost tracking."""

    OK = 'ok'
    WARNING = 'warning'
    EXCEEDED = 'exceeded'
    UNKNOWN = 'unknown'


@dataclass
class ApprovalState:
    """State of pending/blocked approvals."""

    pending_count: int = 0
    blocked_count: int = 0
    auto_approved_count: int = 0
    denied_count: int = 0


@dataclass
class HarnessHealth:
    """Health status of the harness and its components."""

    overall: HealthStatus = HealthStatus.UNKNOWN
    components: dict[str, HealthStatus] = field(default_factory=dict)
    last_check_time: Optional[float] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class BudgetState:
    """Budget state for cost tracking."""

    status: BudgetStatus = BudgetStatus.UNKNOWN
    spent_cents: float = 0.0
    limit_cents: Optional[float] = None
    remaining_cents: Optional[float] = None
    session_cost_cents: float = 0.0


@dataclass
class RecoverableState:
    """State of recoverable operations (undo, resume, etc.)."""

    has_undo_journal: bool = False
    has_checkpoint: bool = False
    has_suspended_session: bool = False
    last_run_id: Optional[str] = None
    last_run_recoverable: bool = False


@dataclass
class CockpitState:
    """Unified operator cockpit state.

    This model aggregates state from multiple sources:
    - Approval system (pending/blocked approvals)
    - Harness health (component status)
    - Budget tracking (cost limits and usage)
    - Recoverable state (undo, checkpoints, suspended sessions)
    """

    approvals: ApprovalState = field(default_factory=ApprovalState)
    harness_health: HarnessHealth = field(default_factory=HarnessHealth)
    budget: BudgetState = field(default_factory=BudgetState)
    recoverable: RecoverableState = field(default_factory=RecoverableState)
    last_updated: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'approvals': {
                'pending_count': self.approvals.pending_count,
                'blocked_count': self.approvals.blocked_count,
                'auto_approved_count': self.approvals.auto_approved_count,
                'denied_count': self.approvals.denied_count,
            },
            'harness_health': {
                'overall': self.harness_health.overall.value,
                'components': {
                    k: v.value for k, v in self.harness_health.components.items()
                },
                'last_check_time': self.harness_health.last_check_time,
                'errors': self.harness_health.errors,
            },
            'budget': {
                'status': self.budget.status.value,
                'spent_cents': self.budget.spent_cents,
                'limit_cents': self.budget.limit_cents,
                'remaining_cents': self.budget.remaining_cents,
                'session_cost_cents': self.budget.session_cost_cents,
            },
            'recoverable': {
                'has_undo_journal': self.recoverable.has_undo_journal,
                'has_checkpoint': self.recoverable.has_checkpoint,
                'has_suspended_session': self.recoverable.has_suspended_session,
                'last_run_id': self.recoverable.last_run_id,
                'last_run_recoverable': self.recoverable.last_run_recoverable,
            },
            'last_updated': self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CockpitState':
        """Create from dictionary."""
        approvals_data = data.get('approvals', {})
        health_data = data.get('harness_health', {})
        budget_data = data.get('budget', {})
        recoverable_data = data.get('recoverable', {})

        return cls(
            approvals=ApprovalState(
                pending_count=approvals_data.get('pending_count', 0),
                blocked_count=approvals_data.get('blocked_count', 0),
                auto_approved_count=approvals_data.get('auto_approved_count', 0),
                denied_count=approvals_data.get('denied_count', 0),
            ),
            harness_health=HarnessHealth(
                overall=HealthStatus(health_data.get('overall', 'unknown')),
                components={
                    k: HealthStatus(v)
                    for k, v in health_data.get('components', {}).items()
                },
                last_check_time=health_data.get('last_check_time'),
                errors=health_data.get('errors', []),
            ),
            budget=BudgetState(
                status=BudgetStatus(budget_data.get('status', 'unknown')),
                spent_cents=budget_data.get('spent_cents', 0.0),
                limit_cents=budget_data.get('limit_cents'),
                remaining_cents=budget_data.get('remaining_cents'),
                session_cost_cents=budget_data.get('session_cost_cents', 0.0),
            ),
            recoverable=RecoverableState(
                has_undo_journal=recoverable_data.get('has_undo_journal', False),
                has_checkpoint=recoverable_data.get('has_checkpoint', False),
                has_suspended_session=recoverable_data.get(
                    'has_suspended_session', False
                ),
                last_run_id=recoverable_data.get('last_run_id'),
                last_run_recoverable=recoverable_data.get(
                    'last_run_recoverable', False
                ),
            ),
            last_updated=data.get('last_updated'),
        )

    def update_timestamp(self) -> None:
        """Update the last_updated timestamp to current time."""
        import time

        self.last_updated = time.time()
