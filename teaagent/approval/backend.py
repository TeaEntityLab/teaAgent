"""Approval backends (canonical import path).

Re-exports from ``teaagent.approval_backend`` so that callers can migrate
to the ``teaagent.approval`` subpackage without breaking legacy imports.
"""

from teaagent.approval_backend import (
    AllowBackend,
    ApprovalBackend,
    ApprovalDecision,
    ApprovalRequest,
    DangerFullAccessBackend,
    PromptBackend,
    ReadOnlyBackend,
    WorkspaceWriteBackend,
    backend_from_mode,
)

__all__ = [
    'AllowBackend',
    'ApprovalBackend',
    'ApprovalDecision',
    'ApprovalRequest',
    'DangerFullAccessBackend',
    'PromptBackend',
    'ReadOnlyBackend',
    'WorkspaceWriteBackend',
    'backend_from_mode',
]
