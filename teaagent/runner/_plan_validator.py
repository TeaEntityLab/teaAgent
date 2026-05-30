"""Plan validation management for AgentRunner."""

from __future__ import annotations

from typing import Any, Optional

from teaagent.governance.plan_gate import assert_write_allowed
from teaagent.policy import ApprovalPolicy, PermissionMode


class PlanValidator:
    """Handles plan validation for tool calls.

    Manages plan-related validation including:
    - Checking if plan is required
    - Validating plan contracts
    - Enforcing plan-before-write policies
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

    def set_plan_contract(self, plan_contract: Any) -> None:
        """Set the plan contract for validation."""
        self._plan_contract = plan_contract

    def set_read_only_lint_errors(self, errors: list[Any]) -> None:
        """Set read-only registry lint errors."""
        self._read_only_registry_lint_errors = errors

    def validate_write_allowed(
        self,
        *,
        tool_name: str,
        context: dict[str, Any],
    ) -> None:
        """Validate that write operations are allowed based on plan policy."""
        assert_write_allowed(
            tool_name=tool_name,
            permission_mode=self.approval_policy.permission_mode,
            context=context,
            require_plan=self.require_plan,
            skip_plan_check=self.skip_plan_check,
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
