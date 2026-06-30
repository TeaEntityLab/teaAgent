"""Unit tests for the shared governed-execution budget layer (ADR 0041 Phase 1).

These assert the extracted enforcement functions behave exactly as the inline
``AgentRunner`` methods did before extraction. The end-to-end budget behavior is
additionally covered through ``AgentRunner`` in ``test_runner_invariants.py``.
"""

from __future__ import annotations

import pytest

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetMonitor
from teaagent.errors import BudgetExceededError
from teaagent.phase_tracker import PhaseTracker
from teaagent.runner._governed_execution import (
    GovernedExecutionContext,
    enforce_budget_warnings,
    enforce_cost_budget,
)


def _context(budget: RunBudget) -> tuple[GovernedExecutionContext, AuditLogger]:
    audit = AuditLogger()
    ctx = GovernedExecutionContext(
        budget=budget,
        phase_tracker=PhaseTracker(),
        audit=audit,
        budget_monitor=BudgetMonitor(budget=budget),
        budget_warning_levels_emitted=set(),
    )
    return ctx, audit


def test_enforce_cost_budget_allows_under_cap() -> None:
    ctx, _ = _context(RunBudget(max_estimated_cost_cents=100))
    enforce_cost_budget(ctx, 50.0)  # no raise


def test_enforce_cost_budget_raises_over_cap() -> None:
    ctx, _ = _context(RunBudget(max_estimated_cost_cents=100))
    with pytest.raises(BudgetExceededError):
        enforce_cost_budget(ctx, 150.0)


def test_enforce_cost_budget_zero_cap_rejects_any_spend() -> None:
    ctx, _ = _context(RunBudget(max_estimated_cost_cents=0))
    enforce_cost_budget(ctx, 0.0)  # zero spend allowed
    with pytest.raises(BudgetExceededError):
        enforce_cost_budget(ctx, 0.01)


def test_enforce_cost_budget_no_cap_never_raises() -> None:
    ctx, _ = _context(RunBudget(max_estimated_cost_cents=None))
    enforce_cost_budget(ctx, 1_000_000.0)  # no cap configured


def test_enforce_budget_warnings_emits_once_per_level() -> None:
    budget = RunBudget(max_estimated_cost_cents=100)
    ctx, audit = _context(budget)

    enforce_budget_warnings(ctx, run_id='r1', cost_cents=60.0)  # 60% crosses 50
    warnings = [e for e in audit.events if e.event_type == 'budget_warning']
    assert any(w.payload.get('level') == 50 for w in warnings)
    assert 50 in ctx.budget_warning_levels_emitted

    before = len([e for e in audit.events if e.event_type == 'budget_warning'])
    enforce_budget_warnings(ctx, run_id='r1', cost_cents=60.0)  # idempotent
    after = len([e for e in audit.events if e.event_type == 'budget_warning'])
    assert after == before
