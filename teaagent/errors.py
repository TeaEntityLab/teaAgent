from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    TRANSIENT = "transient"
    MODEL_LOGIC = "model_logic"
    PERMISSION = "permission"
    SYSTEM = "system"


class AgentHarnessError(Exception):
    category = ErrorCategory.SYSTEM


class BudgetExceededError(AgentHarnessError):
    category = ErrorCategory.MODEL_LOGIC


class ToolValidationError(AgentHarnessError):
    category = ErrorCategory.MODEL_LOGIC


class ToolPermissionError(AgentHarnessError):
    category = ErrorCategory.PERMISSION


class ToolExecutionError(AgentHarnessError):
    category = ErrorCategory.SYSTEM
