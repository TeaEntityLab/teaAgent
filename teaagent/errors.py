from __future__ import annotations

from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    TRANSIENT = 'transient'
    MODEL_LOGIC = 'model_logic'
    PERMISSION = 'permission'
    SYSTEM = 'system'

    def __str__(self) -> str:
        return self.value


class AgentHarnessError(Exception):
    """Base class for all TeaAgent harness errors.

    Attributes
    ----------
    hint:
        A short, actionable remediation message shown to the user.  When set,
        CLI error formatters should append it after the primary message so the
        user knows what to try next.
    """

    category = ErrorCategory.SYSTEM

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(message)
        self.hint: Optional[str] = hint

    def __str__(self) -> str:
        base = super().__str__()
        if self.hint:
            return f'{base}\n  → {self.hint}'
        return base


class BudgetExceededError(AgentHarnessError):
    category = ErrorCategory.MODEL_LOGIC

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(
            message,
            hint=hint
            or (
                'Increase max_iterations / max_tool_calls / max_estimated_cost_cents '
                'in RunBudget, or break the task into smaller subtasks.'
            ),
        )


class ToolValidationError(AgentHarnessError):
    category = ErrorCategory.MODEL_LOGIC

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(
            message,
            hint=hint
            or (
                'The model returned a malformed decision.  '
                'Try re-running with a more capable model or a clearer task description.'
            ),
        )


class ToolPermissionError(AgentHarnessError):
    category = ErrorCategory.PERMISSION

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(
            message,
            hint=hint
            or (
                'Use --permission-mode allow (or prompt/approve the call) '
                'to permit this operation.'
            ),
        )


class ToolExecutionError(AgentHarnessError):
    category = ErrorCategory.SYSTEM

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(
            message,
            hint=hint
            or 'Check that the workspace path is writable and the command is valid.',
        )


class RunCancelledError(AgentHarnessError):
    """Raised when a run is cancelled via a cancel token."""

    category = ErrorCategory.SYSTEM

    def __init__(
        self, message: str = 'run cancelled', *, hint: Optional[str] = None
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or 'Use `teaagent agent resume <run_id>` to continue from the last checkpoint.',
        )
