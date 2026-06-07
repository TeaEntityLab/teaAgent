from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class DenialReasonCode(str, Enum):
    """Categorised reason codes for tool-call denials.

    Each value maps to a specific denial path in the approval pipeline.
    """

    READ_ONLY_MODE = 'read_only_mode'
    WORKSPACE_WRITE_MODE = 'workspace_write_mode'
    FILE_POLICY_DENIED = 'file_policy_denied'
    PLAN_CONTRACT_DENIED = 'plan_contract_denied'
    JIT_USER_DENIED = 'jit_user_denied'
    JIT_NO_APPROVAL = 'jit_no_approval'
    MULTISIG_NO_QUORUM = 'multisig_no_quorum'
    AUTO_MODE_BLOCKED = 'auto_mode_blocked'
    MISSING_STATE = 'missing_state'
    FULL_ACCESS_NOT_ACKNOWLEDGED = 'full_access_not_acknowledged'
    SKILL_WRITE_BLOCKED = 'skill_write_blocked'


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


class ToolValidationError(AgentHarnessError, ValueError):
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

    def __init__(
        self,
        message: str,
        *,
        hint: Optional[str] = None,
        reason_code: Optional[DenialReasonCode] = None,
        approval_request: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or (
                'Use --permission-mode allow (or prompt/approve the call) '
                'to permit this operation.'
            ),
        )
        self.reason_code: Optional[DenialReasonCode] = reason_code
        self.approval_request: Optional[Any] = approval_request


class ToolExecutionError(AgentHarnessError):
    category = ErrorCategory.SYSTEM

    def __init__(self, message: str, *, hint: Optional[str] = None) -> None:
        super().__init__(
            message,
            hint=hint
            or 'Check that the workspace path is writable and the command is valid.',
        )


class InvalidToolDecision(AgentHarnessError):
    """Raised when a tool decision fails structural validation.

    This occurs when the model produces a tool decision JSON that, while
    parseable, lacks required fields or has incorrect types (e.g., null
    arguments, empty tool_name). The decision is rejected before execution
    to prevent silent failures in skill flows and agent runs.
    """

    category = ErrorCategory.MODEL_LOGIC

    def __init__(
        self,
        message: str,
        *,
        hint: Optional[str] = None,
        raw_decision_preview: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint
            or (
                'The model produced a structurally invalid tool decision. '
                'Check the system prompt instructions and retry with a more capable model.'
            ),
        )
        self.raw_decision_preview: Optional[str] = raw_decision_preview


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


class AuditDurabilityError(AgentHarnessError, ValueError):
    """Audit log could not be persisted durably (WS3-001 compliance mode)."""

    category = ErrorCategory.SYSTEM

    def __init__(
        self,
        message: str,
        *,
        cause: Optional[OSError] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            hint=hint or 'Free disk space or unset TEAAGENT_COMPLIANCE_MODE.',
        )
        self.cause = cause
