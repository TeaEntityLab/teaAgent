"""Plan validation management for AgentRunner."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.governance.plan_gate import assert_write_allowed, assert_write_scope
from teaagent.policy import ApprovalPolicy, PermissionMode
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
