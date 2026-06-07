"""Canonical domain types for TeaAgent.

Prefer importing from this package for cross-module type sharing::

    from teaagent.types import AuditEvent, PermissionMode, ToolRegistry

Legacy import paths remain supported during migration.
"""

from teaagent.types.audit import (
    AuditEvent,
    AuditLogger,
    ChainVerificationResult,
    compute_event_hash,
    verify_audit_chain,
)
from teaagent.types.errors import (
    AgentHarnessError,
    BudgetExceededError,
    DenialReasonCode,
    ErrorCategory,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)
from teaagent.types.permissions import ApprovalRequest, JITApprovalState, PermissionMode
from teaagent.types.run import FinalAnswer, RunBudget, RunResult, ToolRequest
from teaagent.types.tools import (
    ToolAnnotations,
    ToolDefinition,
    ToolRateLimit,
    ToolRegistry,
)

__all__ = [
    'AgentHarnessError',
    'ApprovalRequest',
    'AuditEvent',
    'AuditLogger',
    'BudgetExceededError',
    'ChainVerificationResult',
    'DenialReasonCode',
    'ErrorCategory',
    'FinalAnswer',
    'JITApprovalState',
    'PermissionMode',
    'RunBudget',
    'RunResult',
    'ToolAnnotations',
    'ToolDefinition',
    'ToolExecutionError',
    'ToolPermissionError',
    'ToolRateLimit',
    'ToolRegistry',
    'ToolRequest',
    'ToolValidationError',
    'compute_event_hash',
    'verify_audit_chain',
]
