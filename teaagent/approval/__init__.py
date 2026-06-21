"""Consolidated approval subsystem with lazy public exports.

Import from this canonical package during migration from the deprecated root
module paths::

    from teaagent.approval import ApprovalManager, PermissionMode

Legacy paths remain supported through teaagent._compat_modules.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

_EXPORTS: dict[str, tuple[str, str]] = {
    'AllowBackend': ('teaagent.approval.backend', 'AllowBackend'),
    'ApprovalBackend': ('teaagent.approval.backend', 'ApprovalBackend'),
    'ApprovalDecision': ('teaagent.approval.backend', 'ApprovalDecision'),
    'ApprovalHandler': ('teaagent.approval.core', 'ApprovalHandler'),
    'ApprovalManager': ('teaagent.approval.manager', 'ApprovalManager'),
    'ApprovalQueueStore': ('teaagent.approval.queue', 'ApprovalQueueStore'),
    'ApprovalRequest': ('teaagent.approval.core', 'ApprovalRequest'),
    'ApprovalStoreManager': ('teaagent.approval.manager', 'ApprovalStoreManager'),
    'CentralizedApprovalQueue': (
        'teaagent.approval.queue',
        'CentralizedApprovalQueue',
    ),
    'DangerFullAccessBackend': (
        'teaagent.approval.backend',
        'DangerFullAccessBackend',
    ),
    'DiffApprovalHandler': ('teaagent.approval.ui', 'DiffApprovalHandler'),
    'JITApprovalManager': ('teaagent.approval.manager', 'JITApprovalManager'),
    'JITApprovalServer': ('teaagent.approval.server', 'JITApprovalServer'),
    'JITApprovalState': ('teaagent.approval.manager', 'JITApprovalState'),
    'MultiSigQuorumConfig': (
        'teaagent.approval.manager',
        'MultiSigQuorumConfig',
    ),
    'MultiSigQuorumManager': (
        'teaagent.approval.manager',
        'MultiSigQuorumManager',
    ),
    'PeerSignature': ('teaagent.approval.manager', 'PeerSignature'),
    'PermissionMode': ('teaagent.approval.manager', 'PermissionMode'),
    'PermissionModeEnforcer': (
        'teaagent.approval.manager',
        'PermissionModeEnforcer',
    ),
    'PromptBackend': ('teaagent.approval.backend', 'PromptBackend'),
    'ReadOnlyBackend': ('teaagent.approval.backend', 'ReadOnlyBackend'),
    'WorkspaceWriteBackend': (
        'teaagent.approval.backend',
        'WorkspaceWriteBackend',
    ),
    'backend_from_mode': ('teaagent.approval.backend', 'backend_from_mode'),
    'format_denial_message': (
        'teaagent.approval.manager',
        'format_denial_message',
    ),
    'parse_permission_mode': ('teaagent.approval.policy', 'parse_permission_mode'),
}

__all__ = [
    'AllowBackend',
    'ApprovalBackend',
    'ApprovalDecision',
    'ApprovalHandler',
    'ApprovalManager',
    'ApprovalQueueStore',
    'ApprovalRequest',
    'ApprovalStoreManager',
    'CentralizedApprovalQueue',
    'DangerFullAccessBackend',
    'DiffApprovalHandler',
    'JITApprovalManager',
    'JITApprovalServer',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'MultiSigQuorumManager',
    'PeerSignature',
    'PermissionMode',
    'PermissionModeEnforcer',
    'PromptBackend',
    'ReadOnlyBackend',
    'WorkspaceWriteBackend',
    'backend_from_mode',
    'format_denial_message',
    'parse_permission_mode',
]


def __getattr__(name: str) -> Any:
    spec = _EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    module_path, attribute = spec
    value = getattr(importlib.import_module(module_path), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


if TYPE_CHECKING:
    from teaagent.approval.backend import (
        AllowBackend,
        ApprovalBackend,
        ApprovalDecision,
        DangerFullAccessBackend,
        PromptBackend,
        ReadOnlyBackend,
        WorkspaceWriteBackend,
        backend_from_mode,
    )
    from teaagent.approval.core import ApprovalHandler, ApprovalRequest
    from teaagent.approval.manager import (
        ApprovalManager,
        ApprovalStoreManager,
        JITApprovalManager,
        JITApprovalState,
        MultiSigQuorumConfig,
        MultiSigQuorumManager,
        PeerSignature,
        PermissionMode,
        PermissionModeEnforcer,
        format_denial_message,
    )
    from teaagent.approval.policy import parse_permission_mode
    from teaagent.approval.queue import (
        ApprovalQueueStore,
        CentralizedApprovalQueue,
    )
    from teaagent.approval.server import JITApprovalServer
    from teaagent.approval.ui import DiffApprovalHandler
