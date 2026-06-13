"""Plan validation management for AgentRunner."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.governance.plan_gate import assert_write_allowed, assert_write_scope
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner._events import RunEvent, RunEventType
from teaagent.spec_exemption import ExemptionDetector, SpecExemptionReceipt


class PlanValidator:
    """Handles plan validation for tool calls.

    Manages plan-related validation including:
    - Checking if plan is required
    - Validating plan contracts
    - Enforcing plan-before-write policies
    - Spec exemption detection for low-risk tasks
    """

    def __init__(
        self,
        *,
        approval_policy: ApprovalPolicy,
        require_plan: bool = False,
        skip_plan_check: bool = False,
    ) -> None:
        self.approval_policy = approval_policy
        self.require_plan = require_plan
        self.skip_plan_check = skip_plan_check
        self._plan_contract: Any = None
        self._read_only_registry_lint_errors: list[Any] = []
        self._active_exemption: Optional[SpecExemptionReceipt] = None

    def set_plan_contract(self, plan_contract: Any) -> None:
        """Set the plan contract for validation."""
        self._plan_contract = plan_contract

    def set_read_only_lint_errors(self, errors: list[Any]) -> None:
        """Set read-only registry lint errors."""
        self._read_only_registry_lint_errors = errors

    @property
    def active_exemption(self) -> Optional[SpecExemptionReceipt]:
        """The currently active spec exemption, or None."""
        return self._active_exemption

    def validate_with_exemption(
        self,
        task_description: str,
        changed_files: list[str],
        *,
        line_count: Optional[int] = None,
    ) -> Optional[SpecExemptionReceipt]:
        """Auto-detect if a task qualifies for spec exemption.

        If a low-risk pattern is detected, an exemption receipt is granted
        and stored as the active exemption for this validator instance.

        Returns the receipt if exempted, or None if the task should go
        through the full spec ceremony.
        """
        permission_mode = self.approval_policy.permission_mode.value
        receipt = ExemptionDetector.detect(
            task_description=task_description,
            changed_files=changed_files,
            line_count=line_count,
            permission_mode=permission_mode,
        )
        if receipt is not None:
            self._active_exemption = receipt
        return receipt

    def clear_exemption(self) -> None:
        """Clear the active spec exemption."""
        self._active_exemption = None

    def validate_write_allowed(
        self,
        *,
        tool_name: str,
        context: dict[str, Any],
        tool_arguments: dict[str, Any] | None = None,
    ) -> str | None:
        """Validate write operations against plan policy + scope (intent-drift).

        Returns None if allowed, or a drift error message if the write is
        outside the approved plan scope.
        """
        assert_write_allowed(
            tool_name=tool_name,
            permission_mode=self.approval_policy.permission_mode,
            context=context,
            require_plan=self.require_plan,
            skip_plan_check=self.skip_plan_check,
        )

        return assert_write_scope(
            tool_name=tool_name,
            arguments=tool_arguments,
            plan_contract=self._plan_contract,
        )

    def evaluate_write_gate(
        self,
        *,
        tool_name: str,
        context: dict[str, Any],
        tool_arguments: dict[str, Any] | None = None,
    ) -> str | None:
        """Return the first blocking reason for a write tool request.

        This wrapper keeps the runner's pre-write gate evaluation in one place
        while preserving the existing order of checks:

        1. plan-before-write enforcement
        2. plan scope enforcement
        3. read-only registry lint enforcement

        Returns ``None`` when the write can proceed to approval handling.
        """
        drift_error = self.validate_write_allowed(
            tool_name=tool_name,
            context=context,
            tool_arguments=tool_arguments,
        )
        if drift_error:
            return drift_error
        return self.check_read_only_lint_errors()

    def check_read_only_lint_errors(self) -> Optional[str]:
        """Check if there are read-only lint errors that should block execution.

        Returns an error message if errors exist, None otherwise.
        """
        if (
            self.approval_policy.permission_mode == PermissionMode.READ_ONLY
            and self._read_only_registry_lint_errors
        ):
            return (
                'Tool registry has lint errors; read-only runs cannot '
                f'invoke tools ({len(self._read_only_registry_lint_errors)} error(s))'
            )
        return None

    def get_plan_contract(self) -> Any:
        """Get the current plan contract."""
        return self._plan_contract


class PlanGateInterceptor:
    """EventSpine interceptor that enforces the plan gate on TOOL_CALL_REQUESTED.

    Evaluates ``PlanValidator.evaluate_write_gate()`` and raises
    ``ToolPermissionError`` if the write is blocked by plan policy, read-only
    lint, or scope drift.

    In shadow mode (``raise_on_deny=False``) the interceptor records its
    decision without vetoing — used for parity testing before enforcement
    is enabled.
    """

    def __init__(
        self,
        plan_validator: PlanValidator,
        *,
        raise_on_deny: bool = True,
    ) -> None:
        self._pv = plan_validator
        self._raise_on_deny = raise_on_deny
        # Exposed for parity assertions: set after each invocation.
        self.last_decision: str | None = None

    def __call__(self, event: RunEvent) -> None:
        """Evaluate the plan gate for TOOL_CALL_REQUESTED events.

        Args:
            event: The run event.

        Raises:
            ToolPermissionError: If the gate blocks and raise_on_deny is True.
        """
        if event.type != RunEventType.TOOL_CALL_REQUESTED:
            return

        tool_name = event.payload['tool_name']
        arguments = event.payload.get('arguments')
        # Reconstruct minimal context from event payload for plan_contract check.
        context: dict[str, Any] = {}
        plan_contract = event.payload.get('plan_contract')
        if plan_contract is not None:
            context['plan_contract'] = plan_contract

        from teaagent.errors import ToolPermissionError

        try:
            gate_error = self._pv.evaluate_write_gate(
                tool_name=tool_name,
                context=context,
                tool_arguments=arguments,
            )
        except ToolPermissionError as exc:
            # evaluate_write_gate can raise directly from assert_write_allowed.
            self.last_decision = str(exc)
            if self._raise_on_deny:
                raise
            return

        self.last_decision = gate_error
        if gate_error and self._raise_on_deny:
            raise ToolPermissionError(gate_error)
