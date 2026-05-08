from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional, Union
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.context import ContextCompactor
from teaagent.errors import (
    AgentHarnessError,
    BudgetExceededError,
    ErrorCategory,
    ToolPermissionError,
)
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.tools import ToolRegistry


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class FinalAnswer:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


Decision = Union[ToolRequest, FinalAnswer]
DecisionFn = Callable[[dict[str, Any]], Decision]


@dataclass(frozen=True)
class ApprovalRequest:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    annotations: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "reason": self.reason,
            "annotations": self.annotations,
        }


ApprovalHandler = Callable[[ApprovalRequest], bool]


@dataclass(frozen=True)
class RunResult:
    run_id: str
    final_answer: Optional[FinalAnswer]
    iterations: int
    tool_calls: int
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRunner:
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
    ) -> None:
        self.registry = registry
        self.audit = audit
        self.budget = budget or RunBudget()
        self.budget.validate()
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.approval_handler = approval_handler
        self.compactor = compactor
        self.compact_after_observations = compact_after_observations

    def _assert_cost_budget(self, cost_cents: float) -> None:
        if cost_cents > self.budget.max_estimated_cost_cents:
            raise BudgetExceededError("cost budget exceeded")

    def run(self, *, task: str, decide: DecisionFn, run_id: Optional[str] = None) -> RunResult:
        current_run_id = run_id or uuid4().hex
        context: dict[str, Any] = {"task": task, "observations": []}
        iterations = 0
        tool_calls = 0
        cost_cents = 0.0
        self.audit.record("run_started", current_run_id, task=task)

        while iterations < self.budget.max_iterations:
            iterations += 1
            self.audit.record("iteration_started", current_run_id, iteration=iterations)
            try:
                self._assert_cost_budget(cost_cents)
                decision = decide(context)
                cost_cents = context.get("_cost_cents", cost_cents)
                self._assert_cost_budget(cost_cents)
                if isinstance(decision, FinalAnswer):
                    self.audit.record(
                        "run_completed",
                        current_run_id,
                        answer=decision.content,
                        metadata=decision.metadata,
                        cost_cents=cost_cents,
                    )
                    return RunResult(
                        run_id=current_run_id,
                        final_answer=decision,
                        iterations=iterations,
                        tool_calls=tool_calls,
                        status="completed",
                    )

                if tool_calls >= self.budget.max_tool_calls:
                    raise BudgetExceededError("tool-call budget exceeded")

                tool = self.registry.get(decision.tool_name)
                annotations = {
                    "read_only": tool.annotations.read_only,
                    "destructive": tool.annotations.destructive,
                    "idempotent": tool.annotations.idempotent,
                }
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
                            "tool_call_pending_approval",
                            current_run_id,
                            **approval_request.to_dict(),
                        )
                        if self.approval_handler is None:
                            self.audit.record(
                                "run_paused",
                                current_run_id,
                                status="pending_approval",
                                approval=approval_request.to_dict(),
                                cost_cents=cost_cents,
                            )
                            return RunResult(
                                run_id=current_run_id,
                                final_answer=None,
                                iterations=iterations,
                                tool_calls=tool_calls,
                                status="pending_approval",
                                metadata={"approval": approval_request.to_dict()},
                            )
                        if self.approval_handler(approval_request):
                            self.audit.record(
                                "tool_call_approved",
                                current_run_id,
                                call_id=decision.call_id,
                                tool_name=decision.tool_name,
                            )
                        else:
                            self.audit.record(
                                "tool_call_denied",
                                current_run_id,
                                call_id=decision.call_id,
                                tool_name=decision.tool_name,
                            )
                            raise
                    else:
                        self.audit.record(
                            "tool_call_blocked",
                            current_run_id,
                            **approval_request.to_dict(),
                        )
                        raise
                self.audit.record(
                    "tool_call_started",
                    current_run_id,
                    call_id=decision.call_id,
                    tool_name=decision.tool_name,
                    arguments=decision.arguments,
                    annotations=annotations,
                )
                result = self.registry.execute(decision.tool_name, decision.arguments)
                tool_calls += 1
                observation = {
                    "call_id": decision.call_id,
                    "tool_name": decision.tool_name,
                    "result": result,
                }
                context["observations"].append(observation)
                self.audit.record("tool_call_completed", current_run_id, **observation)
                if self.compactor and len(context["observations"]) > self.compact_after_observations:
                    compacted = self.compactor.compact(context)
                    context["observations"] = compacted.context["observations"]
                    context["compacted_summary"] = compacted.summary
                    context["memory_keys"] = compacted.pinned
                    self.audit.record("context_compacted", current_run_id, summary=compacted.summary)
            except AgentHarnessError as exc:
                self.audit.record(
                    "run_failed",
                    current_run_id,
                    category=exc.category,
                    message=str(exc),
                    cost_cents=cost_cents,
                )
                return RunResult(
                    run_id=current_run_id,
                    final_answer=None,
                    iterations=iterations,
                    tool_calls=tool_calls,
                    status=f"failed:{exc.category}",
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                self.audit.record(
                    "run_failed",
                    current_run_id,
                    category=ErrorCategory.SYSTEM,
                    message=str(exc),
                    cost_cents=cost_cents,
                )
                return RunResult(
                    run_id=current_run_id,
                    final_answer=None,
                    iterations=iterations,
                    tool_calls=tool_calls,
                    status=f"failed:{ErrorCategory.SYSTEM}",
                )

        self.audit.record(
            "run_failed",
            current_run_id,
            category=ErrorCategory.MODEL_LOGIC,
            message="iteration budget exceeded",
            cost_cents=cost_cents,
        )
        return RunResult(
            run_id=current_run_id,
            final_answer=None,
            iterations=iterations,
            tool_calls=tool_calls,
            status=f"failed:{ErrorCategory.MODEL_LOGIC}",
        )

    def _can_request_approval(self, destructive: bool) -> bool:
        return destructive and self.approval_policy.permission_mode == PermissionMode.PROMPT
