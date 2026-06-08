"""Consolidated approval subsystem (facade).

Import from this package during migration from scattered approval modules::

    from teaagent.approval import ApprovalManager, PermissionMode

Legacy paths (``teaagent.approval_manager``, etc.) remain supported.
"""

from teaagent.approval.core import (
    ApprovalHandler,
    ApprovalRequest,
    JITApprovalState,
    MultiSigQuorumConfig,
    PeerSignature,
    PermissionMode,
)
from teaagent.approval.manager import (
    ApprovalManager,
    ApprovalStoreManager,
    JITApprovalManager,
    MultiSigQuorumManager,
    PermissionModeEnforcer,
    format_denial_message,
)
from teaagent.approval.policy import parse_permission_mode
from teaagent.approval.queue import ApprovalQueueStore, CentralizedApprovalQueue
from teaagent.approval.server import JITApprovalServer
from teaagent.approval.ui import DiffApprovalHandler

__all__ = [
    'ApprovalHandler',
    'ApprovalManager',
    'ApprovalQueueStore',
    'CentralizedApprovalQueue',
    'ApprovalRequest',
    'ApprovalStoreManager',
    'DiffApprovalHandler',
    'JITApprovalManager',
    'JITApprovalServer',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'MultiSigQuorumManager',
    'PeerSignature',
    'PermissionMode',
    'PermissionModeEnforcer',
    'format_denial_message',
    'parse_permission_mode',
]
