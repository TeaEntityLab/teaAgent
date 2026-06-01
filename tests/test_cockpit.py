"""Tests for operator cockpit state model."""

import time

from teaagent.cockpit import (
    ApprovalState,
    BudgetState,
    BudgetStatus,
    CockpitState,
    HarnessHealth,
    HealthStatus,
    RecoverableState,
)


def test_cockpit_state_serialization():
    """Test CockpitState serialization/deserialization."""
    state = CockpitState(
        approvals=ApprovalState(
            pending_count=5,
            blocked_count=2,
            auto_approved_count=10,
            denied_count=1,
        ),
        harness_health=HarnessHealth(
            overall=HealthStatus.HEALTHY,
            components={
                'tool_registry': HealthStatus.HEALTHY,
                'audit': HealthStatus.HEALTHY,
            },
            last_check_time=time.time(),
            errors=[],
        ),
        budget=BudgetState(
            status=BudgetStatus.OK,
            spent_cents=100.0,
            limit_cents=1000.0,
            remaining_cents=900.0,
            session_cost_cents=50.0,
        ),
        recoverable=RecoverableState(
            has_undo_journal=True,
            has_checkpoint=False,
            has_suspended_session=False,
            last_run_id='test-run-123',
            last_run_recoverable=True,
        ),
    )

    data = state.to_dict()
    restored = CockpitState.from_dict(data)

    assert restored.approvals.pending_count == 5
    assert restored.approvals.blocked_count == 2
    assert restored.harness_health.overall == HealthStatus.HEALTHY
    assert restored.budget.status == BudgetStatus.OK
    assert restored.budget.spent_cents == 100.0
    assert restored.recoverable.has_undo_journal is True
    assert restored.recoverable.last_run_id == 'test-run-123'


def test_cockpit_state_update_timestamp():
    """Test timestamp update."""
    state = CockpitState()
    assert state.last_updated is None

    state.update_timestamp()
    assert state.last_updated is not None
    assert state.last_updated > 0


def test_health_status_enum():
    """Test HealthStatus enum values."""
    assert HealthStatus.HEALTHY.value == 'healthy'
    assert HealthStatus.DEGRADED.value == 'degraded'
    assert HealthStatus.UNHEALTHY.value == 'unhealthy'
    assert HealthStatus.UNKNOWN.value == 'unknown'


def test_budget_status_enum():
    """Test BudgetStatus enum values."""
    assert BudgetStatus.OK.value == 'ok'
    assert BudgetStatus.WARNING.value == 'warning'
    assert BudgetStatus.EXCEEDED.value == 'exceeded'
    assert BudgetStatus.UNKNOWN.value == 'unknown'


def test_empty_cockpit_state():
    """Test empty CockpitState defaults."""
    state = CockpitState()

    assert state.approvals.pending_count == 0
    assert state.approvals.blocked_count == 0
    assert state.harness_health.overall == HealthStatus.UNKNOWN
    assert state.budget.status == BudgetStatus.UNKNOWN
    assert state.budget.spent_cents == 0.0
    assert state.recoverable.has_undo_journal is False
    assert state.last_updated is None


def test_cockpit_state_with_partial_data():
    """Test CockpitState with partial data (missing fields)."""
    data = {
        'approvals': {'pending_count': 3},
        'budget': {'spent_cents': 50.0},
    }

    state = CockpitState.from_dict(data)

    assert state.approvals.pending_count == 3
    assert state.approvals.blocked_count == 0  # default
    assert state.budget.spent_cents == 50.0
    assert state.budget.status == BudgetStatus.UNKNOWN  # default
    assert state.harness_health.overall == HealthStatus.UNKNOWN  # default
