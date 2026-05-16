from __future__ import annotations

import threading
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.auto_mode import AutoModeConfig, AutoModeGuard
from teaagent.budget import RunBudget
from teaagent.context import ContextCompactor
from teaagent.errors import (
    AgentHarnessError,
    BudgetExceededError,
    ErrorCategory,
    RunCancelledError,
    ToolExecutionError,
    ToolPermissionError,
)
from teaagent.file_policy import FilePolicy
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.tools import ToolRegistry

from ._types import ApprovalHandler, ApprovalRequest, DecisionFn, FinalAnswer, RunResult


class AgentRunner:
    """Executes an agent run loop: decide, dispatch tools, enforce budgets, record audit events.

    The runner orchestrates the core agent lifecycle:
    1. Calls the *decide* function with the current context.
    2. On a ``FinalAnswer``, records ``run_completed`` and returns.
    3. On a tool request, validates tool existence, checks policy, dispatches the tool,
       records the observation, and loops.
    4. On budget exhaustion, records ``run_failed`` with a budget‑exceeded error.
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        audit: AuditLogger,
        budget: Optional[RunBudget] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
        approval_handler: Optional[ApprovalHandler] = None,
        compactor: Optional[ContextCompactor] = None,
        compact_after_observations: int = 20,
        checkpoint_store: Any = None,
        cancel_token: Optional[threading.Event] = None,
        file_policy: Optional[FilePolicy] = None,
        auto_mode_config: Optional[AutoModeConfig] = None,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.budget.validate()
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_handler = approval_handler
        self.compactor = compactor
        self.compact_after_observations = compact_after_observations
        self.checkpoint_store = checkpoint_store
        self.cancel_token = cancel_token
        self.file_policy = file_policy
        self.auto_mode_guard: Optional[AutoModeGuard] = None
        if auto_mode_config is not None and auto_mode_config.enabled:
            self.auto_mode_guard = AutoModeGuard(config=auto_mode_config)

    def _assert_cost_budget(self, cost_cents: float) -> None:
        if cost_cents > self.budget.max_estimated_cost_cents:
            raise BudgetExceededError('cost budget exceeded')

    def run(
        self,
        *,
        task: str,
        decide: DecisionFn,
        run_id: Optional[str] = None,
        initial_observations: Optional[list[dict[str, Any]]] = None,
        initial_context_extra: Optional[dict[str, Any]] = None,
    ) -> RunResult:
        current_run_id = run_id or uuid4().hex
        observations: list[dict[str, Any]] = (
            list(initial_observations) if initial_observations else []
        )
        context: dict[str, Any] = {'task': task, 'observations': observations}
        if initial_context_extra:
            context.update(
                {k: v for k, v in initial_context_extra.items() if k != 'task'}
            )
        iterations = 0
        tool_calls = len(observations)
        cost_cents = 0.0
        input_tokens = 0
        output_tokens = 0
        self.audit.record(
            'run_started',
            current_run_id,
            task=task,
            replayed_observations=len(observations),
        )

        while iterations < self.budget.max_iterations:
            iterations += 1
            if self.auto_mode_guard is not None:
                self.auto_mode_guard.record_iteration()
            self.audit.record('iteration_started', current_run_id, iteration=iterations)
            try:
                if self.cancel_token is not None and self.cancel_token.is_set():
                    raise RunCancelledError('run cancelled by cancel token')
                self._assert_cost_budget(cost_cents)
                decision = decide(context)
                cost_cents = context.get('_cost_cents', cost_cents)
                input_tokens = context.get('_input_tokens', input_tokens)
                output_tokens = context.get('_output_tokens', output_tokens)
                self._assert_cost_budget(cost_cents)
                if isinstance(decision, FinalAnswer):
                    self.audit.record(
                        'run_completed',
                        current_run_id,
                        answer=decision.content,
                        metadata=decision.metadata,
                        cost_cents=cost_cents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                    extra_meta: dict[str, Any] = {}
                    if self.auto_mode_guard is not None:
                        extra_meta['auto_mode'] = self.auto_mode_guard.summary()
                    return RunResult(
                        run_id=current_run_id,
                        final_answer=decision,
                        iterations=iterations,
                        tool_calls=tool_calls,
                        status='completed',
                        cost_cents=cost_cents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        metadata=extra_meta if extra_meta else decision.metadata,
                    )

                if tool_calls >= self.budget.max_tool_calls:
                    raise BudgetExceededError('tool-call budget exceeded')

                tool = self.registry.get(decision.tool_name)
                annotations = {
                    'read_only': tool.annotations.read_only,
                    'destructive': tool.annotations.destructive,
                    'idempotent': tool.annotations.idempotent,
                }
                if self.file_policy is not None:
                    self.file_policy.assert_allowed(
                        tool_name=decision.tool_name,
                        arguments=decision.arguments,
                    )
                # Auto mode: block disallowed tools, auto-approve allowed ones
                if self.auto_mode_guard is not None:
                    if not self.auto_mode_guard.is_tool_allowed(decision.tool_name):
                        raise ToolPermissionError(
                            f"Auto mode: tool '{decision.tool_name}' is not allowed"
                        )
                    # In auto mode, skip approval prompts for allowed tools
                    self.approval_policy = ApprovalPolicy(
                        allow_all_destructive=True,
                    )
                try:
                    self.approval_policy.assert_allowed(
                        tool_name=decision.tool_name,
                        call_id=decision.call_id,
                        destructive=tool.annotations.destructive,
                    )
                except ToolPermissionError as exc:
                    approval_request = ApprovalRequest(
                        call_id=decision.call_id,
                        tool_name=decision.tool_name,
                        arguments=decision.arguments,
                        reason=str(exc),
                        annotations=annotations,
                    )
                    if self._can_request_approval(tool.annotations.destructive):
                        self.audit.record(
                            'tool_call_pending_approval',
                            current_run_id,
                            **approval_request.to_dict(),
                        )
                        if self.approval_handler is None:
                            self.audit.record(
                                'run_paused',
                                current_run_id,
                                status='pending_approval',
                                approval=approval_request.to_dict(),
                                cost_cents=cost_cents,
                            )
                            if self.checkpoint_store is not None:
                                self.checkpoint_store.save(current_run_id, context)
                            return RunResult(
                                run_id=current_run_id,
                                final_answer=None,
                                iterations=iterations,
                                tool_calls=tool_calls,
                                status='pending_approval',
                                metadata={'approval': approval_request.to_dict()},
                                cost_cents=cost_cents,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                            )
                        if self.approval_handler(approval_request):
                            self.audit.record(
                                'tool_call_approved',
                                current_run_id,
                                call_id=decision.call_id,
                                tool_name=decision.tool_name,
                            )
                        else:
                            self.audit.record(
                                'tool_call_denied',
                                current_run_id,
                                call_id=decision.call_id,
                                tool_name=decision.tool_name,
                            )
                            raise
                    else:
                        self.audit.record(
                            'tool_call_blocked',
                            current_run_id,
                            **approval_request.to_dict(),
                        )
                        raise
                self.audit.record(
                    'tool_call_started',
                    current_run_id,
                    call_id=decision.call_id,
                    tool_name=decision.tool_name,
                    arguments=decision.arguments,
                    annotations=annotations,
                )
                try:
                    result = self.registry.execute(
                        decision.tool_name, decision.arguments
                    )
                except ToolExecutionError as exc:
                    tool_calls += 1
                    err_observation: dict[str, Any] = {
                        'call_id': decision.call_id,
                        'tool_name': decision.tool_name,
                        'error': str(exc),
                    }
                    context['observations'].append(err_observation)
                    self.audit.record(
                        'tool_call_failed', current_run_id, **err_observation
                    )
                    if self.checkpoint_store is not None:
                        self.checkpoint_store.save(current_run_id, context)
                    continue
                tool_calls += 1
                if self.auto_mode_guard is not None:
                    self.auto_mode_guard.record_tool_call()
                observation = {
                    'call_id': decision.call_id,
                    'tool_name': decision.tool_name,
                    'result': result,
                }
                context['observations'].append(observation)
                self.audit.record('tool_call_completed', current_run_id, **observation)
                if self.checkpoint_store is not None:
                    self.checkpoint_store.save(current_run_id, context)
                if (
                    self.compactor
                    and len(context['observations']) > self.compact_after_observations
                ):
                    compacted = self.compactor.compact(context)
                    context['observations'] = compacted.context['observations']
                    context['compacted_summary'] = compacted.summary
                    context['memory_keys'] = compacted.pinned
                    self.audit.record(
                        'context_compacted', current_run_id, summary=compacted.summary
                    )
            except AgentHarnessError as exc:
                self.audit.record(
                    'run_failed',
                    current_run_id,
                    category=exc.category,
                    message=str(exc),
                    cost_cents=cost_cents,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                return RunResult(
                    run_id=current_run_id,
                    final_answer=None,
                    iterations=iterations,
                    tool_calls=tool_calls,
                    status=f'failed:{exc.category}',
                    error_message=str(exc),
                    cost_cents=cost_cents,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                self.audit.record(
                    'run_failed',
                    current_run_id,
                    category=ErrorCategory.SYSTEM,
                    message=str(exc),
                    cost_cents=cost_cents,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                return RunResult(
                    run_id=current_run_id,
                    final_answer=None,
                    iterations=iterations,
                    tool_calls=tool_calls,
                    status=f'failed:{ErrorCategory.SYSTEM}',
                    error_message=str(exc),
                    cost_cents=cost_cents,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        self.audit.record(
            'run_failed',
            current_run_id,
            category=ErrorCategory.MODEL_LOGIC,
            message='iteration budget exceeded',
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return RunResult(
            run_id=current_run_id,
            final_answer=None,
            iterations=iterations,
            tool_calls=tool_calls,
            status=f'failed:{ErrorCategory.MODEL_LOGIC}',
            error_message='iteration budget exceeded',
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _can_request_approval(self, destructive: bool) -> bool:
        return (
            destructive
            and self.approval_policy.permission_mode == PermissionMode.PROMPT
        )
