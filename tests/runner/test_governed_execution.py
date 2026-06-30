"""Unit tests for the shared governed-execution layer (ADR 0041 Phase 1).

These assert the extracted enforcement behaves exactly as the inline
``AgentRunner`` methods did before extraction: the budget functions directly,
and the authorization delegation via ``AgentRunner._authorize_tool_call``. The
end-to-end behavior is additionally covered through ``AgentRunner`` in
``test_runner_invariants.py`` and the approval/governance suites.
"""

from __future__ import annotations

from typing import Any

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


def test_authorize_tool_call_delegates_to_shared_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``AgentRunner._authorize_tool_call`` forwards verbatim to the shared layer.

    The approval *logic* lives in ``_governed_execution.authorize_tool_call``
    (exercised end-to-end by the approval/governance suites and the live
    differential test); here we lock the wiring so the method cannot silently
    regrow a parallel inline implementation (ADR 0041 Phase 1, G1).
    """
    from teaagent.runner._core import AgentRunner
    from teaagent.runner._types import ToolRequest

    captured: list[tuple[Any, ...]] = []

    def _spy(
        runner: Any,
        decision: Any,
        context: Any,
        run_id: str,
        cost_cents: float,
        *,
        tool: Any,
        annotations: Any,
    ) -> None:
        captured.append(
            (runner, decision, context, run_id, cost_cents, tool, annotations)
        )

    monkeypatch.setattr('teaagent.runner._core.authorize_tool_call', _spy)

    sentinel_runner = object()
    decision = ToolRequest(tool_name='noop', arguments={})
    context: dict[str, Any] = {}
    tool = object()
    annotations: dict[str, Any] = {'destructive': False}

    AgentRunner._authorize_tool_call(
        sentinel_runner,
        decision,
        context,
        'run-1',
        12.5,
        tool=tool,
        annotations=annotations,
    )

    assert captured == [
        (sentinel_runner, decision, context, 'run-1', 12.5, tool, annotations)
    ]
