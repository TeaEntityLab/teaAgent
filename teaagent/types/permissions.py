"""Permission and approval domain types (canonical import path)."""

from teaagent.approval_manager import (
    JITApprovalState,
    PermissionMode,
)
from teaagent.runner._types import ApprovalRequest

__all__ = [
    'ApprovalRequest',
    'JITApprovalState',
    'PermissionMode',
]
