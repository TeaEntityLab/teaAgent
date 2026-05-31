from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.auto_mode import AutoModeConfig
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
from teaagent.plugins import load_plugins
from teaagent.policy import ApprovalPolicy, JITApprovalState, PermissionMode
from teaagent.subagent_run_context import bind_parent_run_id, reset_parent_run_id
from teaagent.tools import ToolRegistry

from ._approval_manager import ApprovalManager
from ._auto_mode_manager import AutoModeManager
from ._plan_validator import PlanValidator
from ._types import ApprovalHandler, DecisionFn, FinalAnswer, RunResult


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
        jit_state: Optional[JITApprovalState] = None,
        workspace_root: Optional[Path] = None,
        require_plan: bool = False,
        skip_plan_check: bool = False,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.budget.validate()
        self.compactor = compactor
        self.compact_after_observations = compact_after_observations
        self.checkpoint_store = checkpoint_store
        self.cancel_token = cancel_token
        self.file_policy = file_policy

        # Initialize manager classes
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_manager = ApprovalManager(
            approval_policy=self.approval_policy,
            approval_handler=approval_handler,
            jit_state=jit_state,
        )
        self.plan_validator = PlanValidator(
            approval_policy=self.approval_policy,
            require_plan=require_plan,
            skip_plan_check=skip_plan_check,
        )
        self.auto_mode_manager = AutoModeManager(
            auto_mode_config=auto_mode_config,
        )

        # Load entry-point plugins if workspace root is provided
        if workspace_root is not None:
            plugin_result = load_plugins(registry)
            if not plugin_result.ok:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f'Failed to load {len(plugin_result.failed)} plugin(s): {plugin_result.failed}'
                )

        # Initialize read-only lint errors for plan validator
        if self.approval_policy.permission_mode == PermissionMode.READ_ONLY:
            from teaagent.governance.tool_lint import lint_registry

            lint_errors = [
                issue for issue in lint_registry(registry) if issue.level == 'error'
            ]
            self.plan_validator.set_read_only_lint_errors(lint_errors)

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
        run_started_extra: Optional[dict[str, Any]] = None,
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
        started_payload: dict[str, Any] = {
            'task': task,
            'replayed_observations': len(observations),
        }
        if run_started_extra:
            started_payload.update(run_started_extra)
        self.audit.record('run_started', current_run_id, **started_payload)

        while iterations < self.budget.max_iterations:
            iterations += 1
            self.auto_mode_manager.record_iteration()
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
                    if self.auto_mode_manager.is_enabled():
                        extra_meta['auto_mode'] = self.auto_mode_manager.summary()
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
                self.plan_validator.validate_write_allowed(
                    tool_name=decision.tool_name,
                    context=context,
                )
                # Auto mode: block disallowed tools, auto-approve allowed ones
                self.auto_mode_manager.validate_tool_allowed(decision.tool_name)
                auto_approve_policy = self.auto_mode_manager.get_auto_approve_policy()
                if auto_approve_policy is not None:
                    self.approval_policy = auto_approve_policy
                try:
                    # Get plan contract from plan validator
                    plan_contract = self.plan_validator.get_plan_contract()

                    # Check read-only lint errors
                    lint_error = self.plan_validator.check_read_only_lint_errors()
                    if lint_error:
                        raise ToolPermissionError(lint_error)

                    self.approval_policy.assert_allowed(
                        tool_name=decision.tool_name,
                        call_id=decision.call_id,
                        destructive=tool.annotations.destructive,
                        arguments=decision.arguments,
                        jit_state=self.approval_manager.jit_state,
                        plan_contract=plan_contract,
                        read_only=tool.annotations.read_only,
                        description=tool.description,
                        handler=tool.handler,
                    )
                except ToolPermissionError as exc:
                    approval_request = self.approval_manager.create_approval_request(
                        call_id=decision.call_id,
                        tool_name=decision.tool_name,
                        arguments=decision.arguments,
                        reason=str(exc),
                        annotations=annotations,
                        run_id=current_run_id,
                    )
                    if self.approval_manager.can_request_approval(
                        tool.annotations.destructive
                    ):
                        approved = self.approval_manager.handle_approval_request(
                            approval_request=approval_request,
                            audit=self.audit,
                            run_id=current_run_id,
                            checkpoint_store=self.checkpoint_store,
                            context=context,
                            cost_cents=cost_cents,
                        )
                        if not approved:
                            if self.approval_manager.approval_handler is None:
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
                            raise
                    else:
                        self.approval_manager.record_blocked(
                            approval_request=approval_request,
                            audit=self.audit,
                            run_id=current_run_id,
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
                    parent_token = bind_parent_run_id(current_run_id)
                    try:
                        result = self.registry.execute(
                            decision.tool_name, decision.arguments
                        )
                    finally:
                        reset_parent_run_id(parent_token)
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
                self.auto_mode_manager.record_tool_call()
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
                    pre_compact_count = len(context['observations'])
                    compacted = self.compactor.compact(context)
                    context['observations'] = compacted.context['observations']
                    context['compacted_summary'] = compacted.summary
                    context['memory_keys'] = compacted.pinned
                    omitted_count = pre_compact_count - len(context['observations'])
                    context['observations'].append(
                        {
                            'role': 'system',
                            'content': f'[System: Context compaction completed. {omitted_count} observations compressed to preserve token budget. Key context preserved in recent observations.]',
                        }
                    )
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
