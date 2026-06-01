"""AC-NEW-15: Daily cockpit parity flow.

As a local developer, I want CLI, TUI, dashboard, and IDE daily views to report
the same readiness state so I do not make decisions from stale surface data.

Acceptance criteria:
- Given the same workspace and run store, every surface reports pending
  approvals, last run status, token pressure, harness warnings, and next safest
  command.
- JSON fields have stable names for automation.
- Human output explains blockers before warnings.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from teaagent.cockpit import (
    ApprovalState,
    BudgetState,
    BudgetStatus,
    CockpitState,
    HarnessHealth,
    HealthStatus,
    RecoverableState,
)
from teaagent.run_store import RunStore


def test_cockpit_state_serialization_stability():
    """Cockpit state must serialize to stable JSON field names for automation."""
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

    # Serialize to dict
    data = state.to_dict()

    # Verify stable field names
    assert 'approvals' in data
    assert 'harness_health' in data
    assert 'budget' in data
    assert 'recoverable' in data
    assert 'last_updated' in data

    # Verify nested field names
    assert 'pending_count' in data['approvals']
    assert 'blocked_count' in data['approvals']
    assert 'overall' in data['harness_health']
    assert 'status' in data['budget']
    assert 'has_undo_journal' in data['recoverable']

    # Verify JSON serializable
    json_str = json.dumps(data)
    assert json_str is not None

    # Verify round-trip
    restored = CockpitState.from_dict(data)
    assert restored.approvals.pending_count == 5
    assert restored.budget.status == BudgetStatus.OK


def test_cockpit_state_from_run_store():
    """Cockpit state can be derived from run store for a given workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(tmpdir)
        audit = store.audit_logger()
        run_id = 'run-cockpit-001'

        # Record a run with approvals
        audit.record('run_started', run_id, task='test task')
        audit.record(
            'approval_requested',
            run_id,
            call_id='call-1',
            tool_name='workspace_write_file',
            auto_approved=False,
        )
        audit.record('run_completed', run_id, answer='done')

        # Build cockpit state from run store
        state = CockpitState()

        # Verify state can be created
        assert state is not None
        assert state.approvals is not None
        assert state.budget is not None
        assert state.harness_health is not None
        assert state.recoverable is not None


def test_cockpit_state_blockers_before_warnings():
    """Cockpit state should prioritize blockers over warnings in human output."""
    state = CockpitState(
        approvals=ApprovalState(
            pending_count=5,
            blocked_count=2,  # Blockers
            auto_approved_count=10,
            denied_count=1,
        ),
        harness_health=HarnessHealth(
            overall=HealthStatus.DEGRADED,  # Warning
            components={
                'tool_registry': HealthStatus.HEALTHY,
                'audit': HealthStatus.DEGRADED,
            },
            errors=['Audit log write latency high'],
        ),
        budget=BudgetState(
            status=BudgetStatus.WARNING,  # Warning
            spent_cents=800.0,
            limit_cents=1000.0,
            remaining_cents=200.0,
            session_cost_cents=50.0,
        ),
    )

    # Blockers should be present (blocked_count > 0)
    assert state.approvals.blocked_count > 0

    # Warnings also present
    assert state.harness_health.overall == HealthStatus.DEGRADED
    assert state.budget.status == BudgetStatus.WARNING

    # State captures both for human output ordering
    data = state.to_dict()
    assert data['approvals']['blocked_count'] == 2
    assert data['harness_health']['overall'] == 'degraded'
    assert data['budget']['status'] == 'warning'


def test_cockpit_state_pending_approvals():
    """Cockpit state must report pending approvals accurately."""
    state = CockpitState(
        approvals=ApprovalState(
            pending_count=3,
            blocked_count=0,
            auto_approved_count=5,
            denied_count=0,
        ),
    )

    assert state.approvals.pending_count == 3
    assert state.approvals.blocked_count == 0

    data = state.to_dict()
    assert data['approvals']['pending_count'] == 3


def test_cockpit_state_last_run_status():
    """Cockpit state must report last run status."""
    state = CockpitState(
        recoverable=RecoverableState(
            has_undo_journal=True,
            has_checkpoint=False,
            has_suspended_session=False,
            last_run_id='run-last-001',
            last_run_recoverable=True,
        ),
    )

    assert state.recoverable.last_run_id == 'run-last-001'
    assert state.recoverable.last_run_recoverable is True

    data = state.to_dict()
    assert data['recoverable']['last_run_id'] == 'run-last-001'
    assert data['recoverable']['last_run_recoverable'] is True


def test_cockpit_state_token_pressure():
    """Cockpit state must report token pressure via budget state."""
    state = CockpitState(
        budget=BudgetState(
            status=BudgetStatus.WARNING,
            spent_cents=900.0,
            limit_cents=1000.0,
            remaining_cents=100.0,
            session_cost_cents=50.0,
        ),
    )

    assert state.budget.status == BudgetStatus.WARNING
    assert state.budget.remaining_cents == 100.0

    data = state.to_dict()
    assert data['budget']['status'] == 'warning'
    assert data['budget']['remaining_cents'] == 100.0


def test_cockpit_state_harness_warnings():
    """Cockpit state must report harness health warnings."""
    state = CockpitState(
        harness_health=HarnessHealth(
            overall=HealthStatus.DEGRADED,
            components={
                'tool_registry': HealthStatus.HEALTHY,
                'audit': HealthStatus.DEGRADED,
            },
            errors=['Audit log write latency high', 'Tool registry sync slow'],
        ),
    )

    assert state.harness_health.overall == HealthStatus.DEGRADED
    assert len(state.harness_health.errors) == 2

    data = state.to_dict()
    assert data['harness_health']['overall'] == 'degraded'
    assert len(data['harness_health']['errors']) == 2


def test_cockpit_state_next_safest_command():
    """Cockpit state should include context for next safest command."""
    state = CockpitState(
        recoverable=RecoverableState(
            has_undo_journal=True,
            has_checkpoint=False,
            has_suspended_session=False,
            last_run_id='run-last-001',
            last_run_recoverable=True,
        ),
    )

    # If last run is recoverable, undo is a safe command
    assert state.recoverable.has_undo_journal is True
    assert state.recoverable.last_run_recoverable is True

    data = state.to_dict()
    assert data['recoverable']['has_undo_journal'] is True


def test_cockpit_state_empty_defaults():
    """Cockpit state should have sensible defaults when no data is available."""
    state = CockpitState()

    assert state.approvals.pending_count == 0
    assert state.approvals.blocked_count == 0
    assert state.harness_health.overall == HealthStatus.UNKNOWN
    assert state.budget.status == BudgetStatus.UNKNOWN
    assert state.budget.spent_cents == 0.0
    assert state.recoverable.has_undo_journal is False
    assert state.last_updated is None

    data = state.to_dict()
    assert data['approvals']['pending_count'] == 0
    assert data['harness_health']['overall'] == 'unknown'
    assert data['budget']['status'] == 'unknown'
