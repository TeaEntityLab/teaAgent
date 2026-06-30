"""Shared governed-execution enforcement layer (ADR 0040 / ADR 0041 Phase 1).

Single home for the per-iteration budget invariants the primary runner enforces:
cost ceilings, phase budgets, and graduated cost warnings. ``AgentRunner``
delegates here so the rules are defined once; subagents inherit them because they
execute through ``AgentRunner`` (``run_chat_agent``) rather than a parallel loop.

Scope note: tool *authorization* (``AgentRunner._authorize_tool_call``) is
intentionally NOT extracted here yet — it reassigns the runner's
``ApprovalPolicy`` and calls back into run-summary emission, so it carries a
larger blast radius and is tracked as a separate, separately risk-reported slice
(ADR 0041 §1.1). This module is the budget dimension of that layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetAction, BudgetMonitor
from teaagent.errors import BudgetExceededError, RunCancelledError
from teaagent.phase_tracker import PhaseTracker


@dataclass
class GovernedExecutionContext:
    """Collaborators the shared budget-enforcement layer operates on.

    Holds references owned by the runner. None of these attributes are
    reassigned during a run, so a context built once at runner construction stays
    in sync with ``AgentRunner`` for the run's lifetime. ``budget_warning_levels_emitted``
    is shared by identity (the same ``set`` object the runner holds) so graduated
    warnings remain idempotent across iterations.
    """

    budget: RunBudget
    phase_tracker: PhaseTracker
    audit: AuditLogger
    budget_monitor: BudgetMonitor
    budget_warning_levels_emitted: set[int]


def enforce_cost_budget(ctx: GovernedExecutionContext, cost_cents: float) -> None:
    """Raise ``BudgetExceededError`` when accumulated cost exceeds the cap."""
    max_cost = ctx.budget.max_estimated_cost_cents
    if max_cost is None:
        return
    # 0 means zero spend allowed - any positive cost exceeds it
    if max_cost == 0:
        if cost_cents > 0:
            raise BudgetExceededError('cost budget exceeded (zero cap)')
        return
    if cost_cents > max_cost:
        raise BudgetExceededError('cost budget exceeded')


def enforce_phase_budget(
    ctx: GovernedExecutionContext,
    *,
    run_id: str,
    cost_cents: float,
) -> None:
    """Raise ``BudgetExceededError`` when the current phase exceeds its budget."""
    tracker = ctx.phase_tracker
    phase = tracker.current_phase
    pb = ctx.budget.phase_budget_for(phase)

    phase_iters = tracker.phase_iterations()
    if phase_iters > pb.max_iterations:
        ctx.audit.record(
            'phase_budget_warning',
            run_id,
            phase=phase.value,
            metric='iterations',
            current=phase_iters,
            limit=pb.max_iterations,
        )
        raise BudgetExceededError(f'phase {phase.value} iteration budget exceeded')

    phase_tools = tracker.phase_tool_calls()
    if phase_tools > pb.max_tool_calls:
        ctx.audit.record(
            'phase_budget_warning',
            run_id,
            phase=phase.value,
            metric='tool_calls',
            current=phase_tools,
            limit=pb.max_tool_calls,
        )
        raise BudgetExceededError(f'phase {phase.value} tool-call budget exceeded')

    phase_cost = tracker.phase_cost_cents(cost_cents)
    if (
        pb.max_estimated_cost_cents is not None
        and phase_cost > pb.max_estimated_cost_cents
    ):
        ctx.audit.record(
            'phase_budget_warning',
            run_id,
            phase=phase.value,
            metric='cost',
            current=phase_cost,
            limit=pb.max_estimated_cost_cents,
        )
        raise BudgetExceededError(f'phase {phase.value} cost budget exceeded')


def enforce_budget_warnings(
    ctx: GovernedExecutionContext,
    *,
    run_id: str,
    cost_cents: float,
) -> None:
    """Emit graduated cost warnings; raise ``RunCancelledError`` at the prompt gate."""
    budget_cap = ctx.budget.max_estimated_cost_cents
    if budget_cap is None:
        return
    # 0 cap is enforced by enforce_cost_budget; no warnings needed
    if budget_cap == 0:
        return
    max_cost = float(budget_cap)
    percent = (cost_cents / max_cost) * 100.0
    for level in (50, 80, 90, 100):
        if percent < level or level in ctx.budget_warning_levels_emitted:
            continue
        ctx.budget_warning_levels_emitted.add(level)

        action = ctx.budget_monitor.check_at_threshold(
            run_id=run_id,
            cost_cents=cost_cents,
            threshold=level,
        )

        ctx.audit.record(
            'budget_warning',
            run_id,
            level=level,
            percent=percent,
            cost_cents=cost_cents,
            max_cost_cents=max_cost,
        )

        if action == BudgetAction.PROMPT_CONFIRM:
            ctx.audit.record(
                'budget_prompt',
                run_id,
                percent=percent,
                cost_cents=cost_cents,
                max_cost_cents=max_cost,
                approved=False,
            )
            raise RunCancelledError('run cancelled: budget at 90%')

        if action == BudgetAction.SUGGEST_READ_ONLY:
            ctx.audit.record(
                'budget_read_only_suggested',
                run_id,
                percent=percent,
                cost_cents=cost_cents,
                max_cost_cents=max_cost,
            )
