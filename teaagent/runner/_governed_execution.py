"""Shared governed-execution enforcement layer (ADR 0040 / ADR 0041 Phase 1).

Single home for the per-iteration governed-execution invariants the primary
runner enforces. ``AgentRunner`` delegates here so the rules are defined once;
subagents inherit them because they execute through ``AgentRunner``
(``run_chat_agent``) rather than a parallel loop.

Two dimensions live here:

- **Budget** — cost ceilings, phase budgets, and graduated cost warnings
  (``enforce_cost_budget`` / ``enforce_phase_budget`` / ``enforce_budget_warnings``),
  operating on an immutable ``GovernedExecutionContext`` of collaborators.
- **Authorization** — spine permission gating, auto-mode scoping,
  preapproved-payload-digest checks, and the approval-policy decision
  (``authorize_tool_call``). It operates on the ``AgentRunner`` itself because it
  reassigns the runner's ``ApprovalPolicy`` (auto-mode scoping) and may call back
  into run-summary emission on a terminal pending-approval denial (ADR 0041 §1.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetAction, BudgetMonitor
from teaagent.errors import (
    BudgetExceededError,
    RunCancelledError,
    ToolPermissionError,
)
from teaagent.phase_tracker import PhaseTracker

from ._events import RunEventType

if TYPE_CHECKING:
    from teaagent.errors import DenialReasonCode
    from teaagent.run_context import RunContext

    from ._core import AgentRunner
    from ._types import ToolRequest


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


def authorize_tool_call(
    runner: AgentRunner,
    decision: ToolRequest,
    context: RunContext,
    run_id: str,
    cost_cents: float,
    *,
    tool: Any,
    annotations: dict[str, Any],
) -> None:
    """Authorize a tool call via spine, auto-mode, and approval policy.

    Shared approval pipeline both execution surfaces use. Operates on ``runner``
    because it reassigns ``runner.approval_policy`` (auto-mode scoping) and may
    call ``runner._emit_summary`` on a terminal pending-approval denial — behaviour
    identical to the prior inline ``AgentRunner._authorize_tool_call`` method.
    """
    if runner.file_policy is not None:
        runner.file_policy.assert_allowed(
            tool_name=decision.tool_name,
            arguments=decision.arguments,
        )

    tcr_payload: dict[str, Any] = {
        'tool_name': decision.tool_name,
    }
    if decision.arguments is not None:
        tcr_payload['arguments'] = decision.arguments
    plan_contract = context.get('plan_contract')
    if plan_contract is not None:
        tcr_payload['plan_contract'] = plan_contract
    try:
        runner.event_spine.emit(
            RunEventType.TOOL_CALL_REQUESTED,
            run_id,
            tcr_payload,
        )
    except ToolPermissionError as exc:
        spine_reason_code: DenialReasonCode | None = getattr(exc, 'reason_code', None)
        reason_code_str = spine_reason_code.value if spine_reason_code else None
        approval_request = runner.approval_manager.create_approval_request(
            call_id=decision.call_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            reason=str(exc),
            annotations=annotations,
            run_id=run_id,
        )
        runner.approval_manager.record_blocked(
            approval_request=approval_request,
            audit=runner.audit,
            run_id=run_id,
            reason_code=reason_code_str,
        )
        raise ToolPermissionError(
            str(exc),
            reason_code=spine_reason_code,
            approval_request=approval_request,
        ) from None

    runner.auto_mode_manager.validate_tool_allowed(decision.tool_name)
    auto_approval = runner.auto_mode_manager.get_auto_approve_policy(
        parent_policy=runner.approval_policy,
        tool_name=decision.tool_name,
        arguments=decision.arguments or {},
        destructive=tool.annotations.destructive,
    )
    auto_mode_approved = auto_approval is not None
    auto_mode_digest: str | None = None
    if auto_approval is not None:
        scoped_policy, auto_mode_digest = auto_approval
        runner.approval_policy = scoped_policy
    try:
        plan_contract = runner.plan_validator.get_plan_contract()
        preapproved_by_payload_digest = (
            not auto_mode_approved
            and tool.annotations.destructive
            and bool(decision.arguments)
            and decision.arguments is not None
            and bool(runner.approval_policy.preapproved_payload_digests)
            and runner._check_payload_digest_approval(
                decision.tool_name, decision.arguments
            )
        )

        runner.approval_policy.assert_allowed(
            tool_name=decision.tool_name,
            call_id=decision.call_id,
            destructive=tool.annotations.destructive,
            arguments=decision.arguments,
            jit_state=runner.approval_manager.jit_state,
            plan_contract=plan_contract,
            read_only=tool.annotations.read_only,
            description=tool.description,
            handler=tool.handler,
        )
        if auto_mode_approved:
            runner.audit.record(
                'tool_call_approved',
                run_id,
                call_id=decision.call_id,
                tool_name=decision.tool_name,
                arguments=decision.arguments,
                authority_type='auto_mode',
                scope='payload_digest',
                auto_approved=True,
                argument_digest=auto_mode_digest,
            )
        if preapproved_by_payload_digest:
            runner.audit.record(
                'tool_call_approved',
                run_id,
                call_id=decision.call_id,
                tool_name=decision.tool_name,
                arguments=decision.arguments,
                authority_type='preapproved_payload_digest',
                approved_by='cli --approve-scoped',
                auto_approved=True,
                scope='payload_digest',
            )
    except ToolPermissionError as exc:
        exc_reason_code: DenialReasonCode | None = getattr(exc, 'reason_code', None)
        reason_code_str = exc_reason_code.value if exc_reason_code else None
        approval_request = runner.approval_manager.create_approval_request(
            call_id=decision.call_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            reason=str(exc),
            annotations=annotations,
            run_id=run_id,
        )
        if runner.approval_manager.can_request_approval(tool.annotations.destructive):
            approved = runner.approval_manager.handle_approval_request(
                approval_request=approval_request,
                audit=runner.audit,
                run_id=run_id,
                checkpoint_store=runner.checkpoint_store,
                context=cast(dict[str, Any], context),
                cost_cents=cost_cents,
                reason_code=reason_code_str,
            )
            if not approved:
                if runner.approval_manager.approval_handler is None:
                    runner._emit_summary(
                        run_id=run_id,
                        cost_cents=cost_cents,
                        input_tokens=context.get('_input_tokens', 0),
                        output_tokens=context.get('_output_tokens', 0),
                    )
                    raise ToolPermissionError(
                        f'Tool call pending approval: {decision.tool_name}',
                        reason_code=exc_reason_code,
                        approval_request=approval_request,
                    ) from None
                raise
        else:
            runner.approval_manager.record_blocked(
                approval_request=approval_request,
                audit=runner.audit,
                run_id=run_id,
                reason_code=reason_code_str,
            )
            raise
