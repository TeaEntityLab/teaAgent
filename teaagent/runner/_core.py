from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.auto_mode import AutoModeConfig
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetAction, BudgetMonitor
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
from teaagent.tool_call_context import (
    ToolCallContext,
    bind_tool_call_context,
    reset_tool_call_context,
)
from teaagent.tools import ToolRegistry

from ._approval_manager import ApprovalManager
from ._auto_mode_manager import AutoModeManager
from ._plan_validator import PlanValidator
from ._types import (
    ApprovalHandler,
    BudgetPromptHandler,
    DecisionFn,
    FinalAnswer,
    RunResult,
)


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
        budget_prompt_handler: Optional[BudgetPromptHandler] = None,
        budget_monitor: Optional[BudgetMonitor] = None,
        compactor: Optional[ContextCompactor] = None,
        compact_after_observations: int = 20,
        compaction_warning_threshold: float = 0.6,
        max_context_tokens: int = 200000,
        checkpoint_store: Any = None,
        cancel_token: Optional[threading.Event] = None,
        file_policy: Optional[FilePolicy] = None,
        auto_mode_config: Optional[AutoModeConfig] = None,
        jit_state: Optional[JITApprovalState] = None,
        workspace_root: Optional[Path] = None,
        require_plan: bool = False,
        skip_plan_check: bool = False,
        show_summary: bool = True,
        scratchpad: Any = None,
        decision_log: Any = None,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.scratchpad = scratchpad
        self.budget.validate()
        self.compactor = compactor
        self.compact_after_observations = compact_after_observations
        self._compaction_warning_threshold = max(0.0, min(1.0, compaction_warning_threshold))
        self._max_context_tokens = max(1, max_context_tokens)
        self.checkpoint_store = checkpoint_store
        self.cancel_token = cancel_token
        self.file_policy = file_policy
        self.show_summary = show_summary
        self.workspace_root = workspace_root
        self.decision_log = decision_log

        # Initialize manager classes
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_manager = ApprovalManager(
            approval_policy=self.approval_policy,
            approval_handler=approval_handler,
            jit_state=jit_state,
        )
        self._budget_prompt_handler = budget_prompt_handler
        self._budget_monitor = budget_monitor or BudgetMonitor(budget=self.budget)
        if self._budget_monitor.on_prompt is None and budget_prompt_handler is not None:
            self._budget_monitor.on_prompt = budget_prompt_handler
        self._budget_warning_levels_emitted: set[int] = set()
        self._budget_prompted = False
        self._compaction_warning_emitted = False
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

    def _check_budget_warnings(self, *, run_id: str, cost_cents: float) -> None:
        max_cost = float(self.budget.max_estimated_cost_cents)
        if max_cost <= 0:
            return
        percent = (cost_cents / max_cost) * 100.0
        for level in (50, 80, 90, 100):
            if percent < level or level in self._budget_warning_levels_emitted:
                continue
            self._budget_warning_levels_emitted.add(level)

            action = self._budget_monitor.check_at_threshold(
                run_id=run_id, cost_cents=cost_cents, threshold=level,
            )

            self.audit.record(
                'budget_warning',
                run_id,
                level=level,
                percent=percent,
                cost_cents=cost_cents,
                max_cost_cents=max_cost,
            )

            if action == BudgetAction.PROMPT_CONFIRM:
                self.audit.record(
                    'budget_prompt',
                    run_id,
                    percent=percent,
                    cost_cents=cost_cents,
                    max_cost_cents=max_cost,
                    approved=False,
                )
                raise RunCancelledError('run cancelled: budget at 90%')

            if action == BudgetAction.SUGGEST_READ_ONLY:
                self.audit.record(
                    'budget_read_only_suggested',
                    run_id,
                    percent=percent,
                    cost_cents=cost_cents,
                    max_cost_cents=max_cost,
                )

    def _check_compaction_warning(
        self, *, context: dict[str, Any], input_tokens: int, output_tokens: int
    ) -> None:
        """Emit a proactive context-compaction warning when estimated usage exceeds threshold.

        The warning fires at most once per run (idempotent). It adds a system
        observation to the context so the model can suggest ``/compact``.
        """
        if self._compaction_warning_emitted:
            return
        if self._compaction_warning_threshold <= 0.0:
            return
        total = input_tokens + output_tokens
        if total <= 0:
            return
        usage_pct = (total / self._max_context_tokens) * 100.0
        threshold_pct = self._compaction_warning_threshold * 100.0
        if usage_pct < threshold_pct:
            return
        self._compaction_warning_emitted = True
        warning_content = (
            f'[System: Context is filling up (estimated {usage_pct:.0f}% used). '
            f'Consider /compact or starting a new session with a summary of progress.]'
        )
        context['observations'].append(
            {'role': 'system', 'content': warning_content}
        )

    def _build_run_summary(
        self,
        *,
        run_id: str,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> str:
        """Build a structured post-run summary string.

        Collects tool-call counts (read vs write), changed files, cost/tokens,
        budget remaining, audit log path, and undo command.
        """
        from teaagent.ergonomics.run_summary import format_run_summary, summarize_run

        run_events: list[dict[str, Any]] = [
            {'event_type': e.event_type, 'payload': e.payload}
            for e in self.audit.events
            if getattr(e, 'run_id', None) == run_id
        ]

        root = str(self.workspace_root) if self.workspace_root else '.'
        budget_cap = self.budget.max_estimated_cost_cents

        summary_dict = summarize_run(
            root=root,
            run_id=run_id,
            events=run_events,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            budget_cap_cents=budget_cap,
        )
        return format_run_summary(summary_dict)

    def _emit_summary(
        self,
        *,
        run_id: str,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        if not self.show_summary:
            return
        if self.workspace_root is None:
            return
        try:
            text = self._build_run_summary(
                run_id=run_id,
                cost_cents=cost_cents,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            logger = logging.getLogger(__name__)
            logger.info(text)
        except Exception:
            logger = logging.getLogger(__name__)
            logger.debug(
                'Failed to build run summary for %s', run_id, exc_info=True
            )

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
        if self.decision_log is not None:
            summary = self.decision_log.inject_summary()
            if summary:
                context['decision_summary'] = summary
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
                self._check_budget_warnings(
                    run_id=current_run_id, cost_cents=cost_cents
                )
                self._check_compaction_warning(
                    context=context,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
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
                    self._emit_summary(
                        run_id=current_run_id,
                        cost_cents=cost_cents,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
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
                    reason_code = getattr(exc, 'reason_code', None)
                    reason_code_str = reason_code.value if reason_code else None
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
                            reason_code=reason_code_str,
                        )
                        if not approved:
                            if self.approval_manager.approval_handler is None:
                                self._emit_summary(
                                    run_id=current_run_id,
                                    cost_cents=cost_cents,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                )
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
                            reason_code=reason_code_str,
                        )
                        raise
                self.audit.record(
                    'tool_call_started',
                    current_run_id,
                    call_id=decision.call_id,
                    tool_name=decision.tool_name,
                    arguments=decision.arguments,
                    annotations=annotations,
                    reasoning=decision.reasoning if decision.reasoning else None,
                )
                try:
                    parent_token = bind_parent_run_id(current_run_id)
                    tool_ctx_token = bind_tool_call_context(
                        ToolCallContext(
                            audit=self.audit,
                            run_id=current_run_id,
                            call_id=decision.call_id,
                        )
                    )
                    try:
                        result = self.registry.execute(
                            decision.tool_name, decision.arguments
                        )
                    finally:
                        reset_tool_call_context(tool_ctx_token)
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
                self._emit_summary(
                    run_id=current_run_id,
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
                self._emit_summary(
                    run_id=current_run_id,
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
        self._emit_summary(
            run_id=current_run_id,
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
