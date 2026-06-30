from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional, cast
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.auto_mode import AutoModeConfig
from teaagent.budget import RunBudget
from teaagent.budget_monitor import BudgetMonitor
from teaagent.context import ContextCompactor
from teaagent.errors import (
    AgentHarnessError,
    BudgetExceededError,
    DenialReasonCode,
    ErrorCategory,
    InvalidToolDecision,
    RunCancelledError,
    ToolExecutionError,
    ToolPermissionError,
)
from teaagent.file_policy import FilePolicy
from teaagent.long_result_envelope import DEFAULT_MAX_PREVIEW_BYTES, store_long_result
from teaagent.phase_tracker import PhaseTracker
from teaagent.plugin_system import discover_and_load_all
from teaagent.policy import ApprovalPolicy, JITApprovalState, PermissionMode
from teaagent.proof_of_use import build_proof_of_use, emit_proof_of_use_audit
from teaagent.run_context import RunContext
from teaagent.run_logging import setup_run_logging, teardown_run_logging
from teaagent.subagent_run_context import (
    bind_parent_run_id,
    bind_parent_session_cost_cents,
    reset_parent_run_id,
    reset_parent_session_cost_cents,
)
from teaagent.tool_call_context import (
    ToolCallContext,
    bind_tool_call_context,
    reset_tool_call_context,
)
from teaagent.tools import ToolRegistry

logger = logging.getLogger(__name__)

from ._approval_manager import RunnerApprovalCoordinator  # noqa: E402
from ._auto_mode_manager import AutoModeManager  # noqa: E402
from ._events import EventSpine, RunEventType, register_audit_consumer  # noqa: E402
from ._governed_execution import (  # noqa: E402
    GovernedExecutionContext,
    enforce_budget_warnings,
    enforce_cost_budget,
    enforce_phase_budget,
)
from ._plan_validator import PlanGateInterceptor, PlanValidator  # noqa: E402
from ._types import (  # noqa: E402
    ApprovalHandler,
    BudgetPromptHandler,
    DecisionFn,
    FinalAnswer,
    RunResult,
    ToolRequest,
)

UsageReader = Callable[[], tuple[float, int, int]]


def validate_tool_decision(decision_json: dict) -> tuple[bool, str]:
    """Validate the structural integrity of a tool decision JSON dict.

    Checks required fields and types before the decision reaches the
    execution layer. Returns ``(True, "")`` when valid, or
    ``(False, reason)`` when invalid.
    """
    if not isinstance(decision_json, dict):
        return False, 'decision is not a dict'

    tool_name = decision_json.get('tool_name')
    if tool_name is None:
        return False, 'missing required field: tool_name'
    if not isinstance(tool_name, str):
        return False, f'tool_name must be string, got {type(tool_name).__name__}'
    if not tool_name.strip():
        return False, 'tool_name must be non-empty'

    arguments = decision_json.get('arguments')
    if arguments is None:
        return False, 'missing required field: arguments'
    if not isinstance(arguments, dict):
        return False, f'arguments must be dict, got {type(arguments).__name__}'

    return True, ''


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
        phase_tracker: Optional[PhaseTracker] = None,
        usage_reader: Optional[UsageReader] = None,
        event_spine: Optional[EventSpine] = None,
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.scratchpad = scratchpad
        self.budget.validate()
        self.phase_tracker = phase_tracker or PhaseTracker()
        self.compactor = compactor
        self.compact_after_observations = compact_after_observations
        self._compaction_warning_threshold = max(
            0.0, min(1.0, compaction_warning_threshold)
        )
        self._max_context_tokens = max(1, max_context_tokens)
        self.checkpoint_store = checkpoint_store
        self.cancel_token = cancel_token
        self.file_policy = file_policy
        self.show_summary = show_summary
        self.workspace_root = workspace_root
        self.decision_log = decision_log
        self._usage_reader = usage_reader
        self.event_spine = event_spine or EventSpine()
        register_audit_consumer(self.event_spine, self.audit)

        # Initialize manager classes
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_manager = RunnerApprovalCoordinator(
            approval_policy=self.approval_policy,
            approval_handler=approval_handler,
            jit_state=jit_state,
            workspace_root=workspace_root,
        )
        self._budget_prompt_handler = budget_prompt_handler
        self._budget_monitor = budget_monitor or BudgetMonitor(budget=self.budget)
        if self._budget_monitor.on_prompt is None and budget_prompt_handler is not None:
            self._budget_monitor.on_prompt = budget_prompt_handler
        self._budget_warning_levels_emitted: set[int] = set()
        self._budget_prompted = False
        self._compaction_warning_emitted = False
        self._governed_execution = GovernedExecutionContext(
            budget=self.budget,
            phase_tracker=self.phase_tracker,
            audit=self.audit,
            budget_monitor=self._budget_monitor,
            budget_warning_levels_emitted=self._budget_warning_levels_emitted,
        )
        self.plan_validator = PlanValidator(
            approval_policy=self.approval_policy,
            require_plan=require_plan,
            skip_plan_check=skip_plan_check,
        )

        # M3-T002 Slice B: the plan gate is now the authoritative EventSpine
        # interceptor (enforce mode). It vetoes TOOL_CALL_REQUESTED by raising
        # ToolPermissionError when the write is blocked by plan policy or
        # read-only lint. Slice A proved its decision equals the (now removed)
        # inline gate per reason code.
        self._plan_gate_interceptor = PlanGateInterceptor(
            self.plan_validator,
            raise_on_deny=True,
        )
        self.event_spine.register_interceptor(
            self._plan_gate_interceptor,
            name='plan_gate',
        )

        self.auto_mode_manager = AutoModeManager(
            auto_mode_config=auto_mode_config,
        )

        # Load plugins (entry-points + file-based manifests) if workspace root is provided
        if workspace_root is not None:
            plugin_result = discover_and_load_all(
                registry, workspace_root=workspace_root
            )
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
        enforce_cost_budget(self._governed_execution, cost_cents)

    def _read_usage(
        self,
        context: RunContext,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[float, int, int]:
        """Return authoritative usage totals for budget enforcement (SEC-05)."""
        if self._usage_reader is not None:
            return self._usage_reader()
        reported_cost = context.get('_cost_cents', cost_cents)
        if reported_cost >= cost_cents:
            cost_cents = float(reported_cost)
        reported_in = context.get('_input_tokens', input_tokens)
        if reported_in >= input_tokens:
            input_tokens = int(reported_in)
        reported_out = context.get('_output_tokens', output_tokens)
        if reported_out >= output_tokens:
            output_tokens = int(reported_out)
        return cost_cents, input_tokens, output_tokens

    def _check_phase_budget(
        self,
        *,
        run_id: str,
        cost_cents: float,
        tool_calls: int,
    ) -> None:
        enforce_phase_budget(
            self._governed_execution,
            run_id=run_id,
            cost_cents=cost_cents,
        )

    def _check_budget_warnings(self, *, run_id: str, cost_cents: float) -> None:
        enforce_budget_warnings(
            self._governed_execution,
            run_id=run_id,
            cost_cents=cost_cents,
        )

    def _check_compaction_warning(
        self, *, context: RunContext, input_tokens: int, output_tokens: int
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
        context['observations'].append({'role': 'system', 'content': warning_content})

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
        # Teardown per-run logging context regardless of summary display settings.
        teardown_run_logging()
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
            logger.debug('Failed to build run summary for %s', run_id, exc_info=True)

    def _initialize_run_state(
        self,
        task: str,
        run_id: Optional[str],
        initial_observations: Optional[list[dict[str, Any]]],
        initial_context_extra: Optional[dict[str, Any]],
        run_started_extra: Optional[dict[str, Any]],
    ) -> tuple[str, RunContext, int, float, int, int]:
        """Initialize run state and context.

        Returns:
            Tuple of (run_id, context, tool_calls, cost_cents, input_tokens, output_tokens)
        """
        current_run_id = run_id or uuid4().hex
        observations: list[dict[str, Any]] = (
            list(initial_observations) if initial_observations else []
        )
        context: RunContext = {'task': task, 'observations': observations}
        if initial_context_extra:
            for k, v in initial_context_extra.items():
                if k != 'task':
                    cast(dict[str, Any], context)[k] = v
        if self.decision_log is not None:
            summary = self.decision_log.inject_summary()
            if summary:
                context['decision_summary'] = summary
        tool_calls = len(observations)
        cost_cents = 0.0
        self.phase_tracker.set_cost_start(cost_cents)
        input_tokens = 0
        output_tokens = 0
        started_payload: dict[str, Any] = {
            'task': task,
            'replayed_observations': len(observations),
        }
        if run_started_extra:
            started_payload.update(run_started_extra)
        self.event_spine.emit(RunEventType.RUN_STARTED, current_run_id, started_payload)
        return (
            current_run_id,
            context,
            tool_calls,
            cost_cents,
            input_tokens,
            output_tokens,
        )

    def _handle_final_answer(
        self,
        decision: FinalAnswer,
        run_id: str,
        iterations: int,
        tool_calls: int,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> RunResult:
        """Handle a FinalAnswer decision and return the run result."""
        proof_bundle = build_proof_of_use(self.audit.events, decision.content)
        enriched_metadata: dict[str, Any] = {**decision.metadata}
        if proof_bundle.proofs:
            enriched_metadata['proof_of_use'] = proof_bundle.to_dict()
            self.audit.record(
                'proof_of_use_collected',
                run_id,
                **emit_proof_of_use_audit(proof_bundle),
            )

        run_completed_payload = {
            'answer': decision.content,
            'metadata': enriched_metadata,
            'cost_cents': cost_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }
        self.event_spine.emit(RunEventType.RUN_COMPLETED, run_id, run_completed_payload)
        extra_meta: dict[str, Any] = {}
        if self.auto_mode_manager.is_enabled():
            extra_meta['auto_mode'] = self.auto_mode_manager.summary()
        self._emit_summary(
            run_id=run_id,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return RunResult(
            run_id=run_id,
            final_answer=FinalAnswer(
                content=decision.content,
                metadata=enriched_metadata,
            ),
            iterations=iterations,
            tool_calls=tool_calls,
            status='completed',
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=extra_meta if extra_meta else enriched_metadata,
        )

    def _handle_harness_error(
        self,
        exc: AgentHarnessError,
        run_id: str,
        iterations: int,
        tool_calls: int,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> RunResult:
        """Handle an AgentHarnessError and return the run result."""
        run_failed_payload = {
            'category': exc.category,
            'message': str(exc),
            'cost_cents': cost_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }
        self.event_spine.emit(RunEventType.RUN_FAILED, run_id, run_failed_payload)
        self._emit_summary(
            run_id=run_id,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=iterations,
            tool_calls=tool_calls,
            status=f'failed:{exc.category}',
            error_message=str(exc),
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _handle_system_error(
        self,
        exc: Exception,
        run_id: str,
        iterations: int,
        tool_calls: int,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> RunResult:
        """Handle a system error and return the run result."""
        system_failed_payload = {
            'category': ErrorCategory.SYSTEM,
            'message': str(exc),
            'cost_cents': cost_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }
        self.event_spine.emit(RunEventType.RUN_FAILED, run_id, system_failed_payload)
        self._emit_summary(
            run_id=run_id,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=iterations,
            tool_calls=tool_calls,
            status=f'failed:{ErrorCategory.SYSTEM}',
            error_message=str(exc),
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _check_payload_digest_approval(
        self, tool_name: str, arguments: dict[str, Any] | None
    ) -> bool:
        """Check if this tool+args combo is approved by a preapproved payload digest."""
        if not arguments or not self.approval_policy.preapproved_payload_digests:
            return False
        from teaagent.policy import compute_scoped_payload_digest

        digest = compute_scoped_payload_digest(tool_name, arguments)
        return digest in self.approval_policy.preapproved_payload_digests

    def _authorize_tool_call(
        self,
        decision: ToolRequest,
        context: RunContext,
        run_id: str,
        cost_cents: float,
        *,
        tool: Any,
        annotations: dict[str, Any],
    ) -> None:
        """Authorize a tool call via spine, auto-mode, and approval policy."""
        if self.file_policy is not None:
            self.file_policy.assert_allowed(
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
            self.event_spine.emit(
                RunEventType.TOOL_CALL_REQUESTED,
                run_id,
                tcr_payload,
            )
        except ToolPermissionError as exc:
            spine_reason_code: DenialReasonCode | None = getattr(
                exc, 'reason_code', None
            )
            reason_code_str = spine_reason_code.value if spine_reason_code else None
            approval_request = self.approval_manager.create_approval_request(
                call_id=decision.call_id,
                tool_name=decision.tool_name,
                arguments=decision.arguments,
                reason=str(exc),
                annotations=annotations,
                run_id=run_id,
            )
            self.approval_manager.record_blocked(
                approval_request=approval_request,
                audit=self.audit,
                run_id=run_id,
                reason_code=reason_code_str,
            )
            raise ToolPermissionError(
                str(exc),
                reason_code=spine_reason_code,
                approval_request=approval_request,
            ) from None

        self.auto_mode_manager.validate_tool_allowed(decision.tool_name)
        auto_approval = self.auto_mode_manager.get_auto_approve_policy(
            parent_policy=self.approval_policy,
            tool_name=decision.tool_name,
            arguments=decision.arguments or {},
            destructive=tool.annotations.destructive,
        )
        auto_mode_approved = auto_approval is not None
        auto_mode_digest: str | None = None
        if auto_approval is not None:
            scoped_policy, auto_mode_digest = auto_approval
            self.approval_policy = scoped_policy
        try:
            plan_contract = self.plan_validator.get_plan_contract()
            preapproved_by_payload_digest = (
                not auto_mode_approved
                and tool.annotations.destructive
                and bool(decision.arguments)
                and decision.arguments is not None
                and bool(self.approval_policy.preapproved_payload_digests)
                and self._check_payload_digest_approval(
                    decision.tool_name, decision.arguments
                )
            )

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
            if auto_mode_approved:
                self.audit.record(
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
                self.audit.record(
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
            approval_request = self.approval_manager.create_approval_request(
                call_id=decision.call_id,
                tool_name=decision.tool_name,
                arguments=decision.arguments,
                reason=str(exc),
                annotations=annotations,
                run_id=run_id,
            )
            if self.approval_manager.can_request_approval(tool.annotations.destructive):
                approved = self.approval_manager.handle_approval_request(
                    approval_request=approval_request,
                    audit=self.audit,
                    run_id=run_id,
                    checkpoint_store=self.checkpoint_store,
                    context=cast(dict[str, Any], context),
                    cost_cents=cost_cents,
                    reason_code=reason_code_str,
                )
                if not approved:
                    if self.approval_manager.approval_handler is None:
                        self._emit_summary(
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
                self.approval_manager.record_blocked(
                    approval_request=approval_request,
                    audit=self.audit,
                    run_id=run_id,
                    reason_code=reason_code_str,
                )
                raise

    def _dispatch_tool_call(
        self,
        decision: ToolRequest,
        context: RunContext,
        run_id: str,
        tool_calls: int,
        cost_cents: float,
        annotations: dict[str, Any],
    ) -> tuple[int, RunContext, Any | None, float]:
        """Execute an authorized tool call.

        Returns ``(tool_calls, context, result, started_at)``. When
        ``result`` is ``None`` the execution error path already updated
        state and the caller should return immediately.
        """
        self.audit.record(
            'tool_call_started',
            run_id,
            call_id=decision.call_id,
            tool_name=decision.tool_name,
            arguments=decision.arguments,
            annotations=annotations,
            reasoning=decision.reasoning if decision.reasoning else None,
        )
        tool_started_at = time.monotonic()
        try:
            parent_token = bind_parent_run_id(run_id)
            cost_token = bind_parent_session_cost_cents(cost_cents)
            tool_ctx_token = bind_tool_call_context(
                ToolCallContext(
                    audit=self.audit,
                    run_id=run_id,
                    call_id=decision.call_id,
                )
            )
            try:
                result = self.registry.execute(decision.tool_name, decision.arguments)
            finally:
                reset_tool_call_context(tool_ctx_token)
                reset_parent_session_cost_cents(cost_token)
                reset_parent_run_id(parent_token)
        except ToolExecutionError as exc:
            tool_calls += 1
            err_observation: dict[str, Any] = {
                'call_id': decision.call_id,
                'tool_name': decision.tool_name,
                'error': str(exc),
                'duration_ms': round((time.monotonic() - tool_started_at) * 1000.0, 2),
            }
            context['observations'].append(err_observation)
            self.event_spine.emit(
                RunEventType.TOOL_CALL_FAILED, run_id, err_observation
            )
            if self.checkpoint_store is not None:
                self.checkpoint_store.save(run_id, context)
            return tool_calls, context, None, tool_started_at

        return tool_calls, context, result, tool_started_at

    def _process_tool_result(
        self,
        decision: ToolRequest,
        context: RunContext,
        run_id: str,
        tool_calls: int,
        result: Any,
        started_at: float,
    ) -> tuple[int, RunContext]:
        """Record a successful tool result and optionally compact context."""
        _long_meta: dict[str, Any] | None = None
        if (
            isinstance(result, str)
            and self.workspace_root is not None
            and len(result.encode('utf-8')) > DEFAULT_MAX_PREVIEW_BYTES
        ):
            envelope = store_long_result(
                self.workspace_root,
                run_id,
                decision.call_id,
                result,
                max_preview_bytes=DEFAULT_MAX_PREVIEW_BYTES,
            )
            observation_result = envelope.preview
            _long_meta = {
                'result_truncated': envelope.truncated,
                'result_total_bytes': envelope.total_bytes,
                'result_preview_bytes': envelope.preview_bytes,
                'result_artifact_path': envelope.artifact_path,
                'result_content_hash': envelope.content_hash,
                'result_cursor': envelope.cursor,
            }
        else:
            observation_result = result

        tool_calls += 1
        self.auto_mode_manager.record_tool_call()
        duration_ms = round((time.monotonic() - started_at) * 1000.0, 2)
        logger.info(
            '%s completed',
            decision.tool_name,
            extra={
                'event': 'tool_executed',
                'duration_ms': duration_ms,
                'tool_name': decision.tool_name,
            },
        )
        observation: dict[str, Any] = {
            'call_id': decision.call_id,
            'tool_name': decision.tool_name,
            'result': observation_result,
            'duration_ms': duration_ms,
        }
        if _long_meta is not None:
            observation.update(_long_meta)
        context['observations'].append(observation)
        self.event_spine.emit(RunEventType.TOOL_CALL_COMPLETED, run_id, observation)
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(run_id, context)
        if (
            self.compactor
            and len(context['observations']) > self.compact_after_observations
        ):
            pre_compact_count = len(context['observations'])
            compacted = self.compactor.compact(cast(dict[str, Any], context))
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
            self.audit.record('context_compacted', run_id, summary=compacted.summary)
        return tool_calls, context

    def _execute_tool_decision(
        self,
        decision: ToolRequest,
        context: RunContext,
        run_id: str,
        tool_calls: int,
        cost_cents: float,
    ) -> tuple[int, RunContext]:
        """Execute a tool decision with approval flow and return updated state."""
        tool = self.registry.get(decision.tool_name)
        annotations = {
            'read_only': tool.annotations.read_only,
            'destructive': tool.annotations.destructive,
            'idempotent': tool.annotations.idempotent,
        }
        self._authorize_tool_call(
            decision,
            context,
            run_id,
            cost_cents,
            tool=tool,
            annotations=annotations,
        )
        tool_calls, context, result, started_at = self._dispatch_tool_call(
            decision,
            context,
            run_id,
            tool_calls,
            cost_cents,
            annotations,
        )
        if result is None:
            return tool_calls, context
        return self._process_tool_result(
            decision,
            context,
            run_id,
            tool_calls,
            result,
            started_at,
        )

    def _handle_budget_exceeded(
        self,
        run_id: str,
        iterations: int,
        tool_calls: int,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> RunResult:
        """Handle budget exceeded case and return the run result."""
        budget_exceeded_payload = {
            'category': ErrorCategory.MODEL_LOGIC,
            'message': 'iteration budget exceeded',
            'cost_cents': cost_cents,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }
        self.event_spine.emit(RunEventType.RUN_FAILED, run_id, budget_exceeded_payload)
        self._emit_summary(
            run_id=run_id,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=iterations,
            tool_calls=tool_calls,
            status=f'failed:{ErrorCategory.MODEL_LOGIC}',
            error_message='iteration budget exceeded',
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _execute_run_loop(
        self,
        *,
        task: str,
        decide: DecisionFn,
        current_run_id: str,
        context: RunContext,
        tool_calls: int,
        cost_cents: float,
        input_tokens: int,
        output_tokens: int,
    ) -> RunResult:
        """Execute the main iteration loop for a run."""
        iterations = 0

        while iterations < self.budget.max_iterations:
            iterations += 1
            self.auto_mode_manager.record_iteration()
            iteration_payload = {'iteration': iterations}
            self.event_spine.emit(
                RunEventType.ITERATION_STARTED, current_run_id, iteration_payload
            )
            self.phase_tracker.record_iteration()
            try:
                if self.cancel_token is not None and self.cancel_token.is_set():
                    raise RunCancelledError('run cancelled by cancel token')
                self._check_phase_budget(
                    run_id=current_run_id,
                    cost_cents=cost_cents,
                    tool_calls=tool_calls,
                )
                self._assert_cost_budget(cost_cents)
                decision = decide(cast(dict[str, Any], context))
                cost_cents, input_tokens, output_tokens = self._read_usage(
                    context, cost_cents, input_tokens, output_tokens
                )
                self._check_phase_budget(
                    run_id=current_run_id,
                    cost_cents=cost_cents,
                    tool_calls=tool_calls,
                )
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
                    return self._handle_final_answer(
                        decision,
                        current_run_id,
                        iterations,
                        tool_calls,
                        cost_cents,
                        input_tokens,
                        output_tokens,
                    )

                self._check_phase_budget(
                    run_id=current_run_id,
                    cost_cents=cost_cents,
                    tool_calls=tool_calls,
                )
                if tool_calls >= self.budget.max_tool_calls:
                    raise BudgetExceededError('tool-call budget exceeded')

                if isinstance(decision, ToolRequest):
                    valid, reason = validate_tool_decision(
                        {
                            'tool_name': decision.tool_name,
                            'arguments': decision.arguments,
                            'call_id': decision.call_id,
                        }
                    )
                    if not valid:
                        preview = str(decision.arguments)[:120]
                        self.audit.record(
                            'tool_decision_invalid',
                            current_run_id,
                            tool_name=decision.tool_name,
                            reason=reason,
                            raw_decision_preview=preview,
                        )
                        raise InvalidToolDecision(
                            reason,
                            raw_decision_preview=preview,
                        )

                tool_calls, context = self._execute_tool_decision(
                    decision,
                    context,
                    current_run_id,
                    tool_calls,
                    cost_cents,
                )
                self.phase_tracker.record_tool_call()
            except ToolPermissionError as exc:
                approval_metadata = {}
                if hasattr(exc, 'reason_code') and exc.reason_code:
                    approval_metadata['reason_code'] = exc.reason_code.value
                if hasattr(exc, 'approval_request') and exc.approval_request:
                    approval_metadata['call_id'] = exc.approval_request.call_id
                    approval_metadata['tool_name'] = exc.approval_request.tool_name
                    approval_metadata['arguments'] = exc.approval_request.arguments
                teardown_run_logging()
                return RunResult(
                    run_id=current_run_id,
                    final_answer=None,
                    iterations=iterations,
                    tool_calls=tool_calls,
                    status='pending_approval',
                    error_message=str(exc),
                    metadata={'approval': approval_metadata},
                    cost_cents=cost_cents,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except AgentHarnessError as exc:
                return self._handle_harness_error(
                    exc,
                    current_run_id,
                    iterations,
                    tool_calls,
                    cost_cents,
                    input_tokens,
                    output_tokens,
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                return self._handle_system_error(
                    exc,
                    current_run_id,
                    iterations,
                    tool_calls,
                    cost_cents,
                    input_tokens,
                    output_tokens,
                )

        return self._handle_budget_exceeded(
            current_run_id,
            iterations,
            tool_calls,
            cost_cents,
            input_tokens,
            output_tokens,
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
        current_run_id, context, tool_calls, cost_cents, input_tokens, output_tokens = (
            self._initialize_run_state(
                task,
                run_id,
                initial_observations,
                initial_context_extra,
                run_started_extra,
            )
        )
        setup_run_logging(current_run_id)
        return self._execute_run_loop(
            task=task,
            decide=decide,
            current_run_id=current_run_id,
            context=context,
            tool_calls=tool_calls,
            cost_cents=cost_cents,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
