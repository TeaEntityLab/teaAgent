"""Core approval data types (canonical import path)."""

from teaagent.approval_manager import (
    ApprovalRequest,
    JITApprovalState,
    MultiSigQuorumConfig,
    PeerSignature,
    PermissionMode,
)

__all__ = [
    'ApprovalRequest',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'PeerSignature',
    'PermissionMode',
]
