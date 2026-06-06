"""Durable coordination backends for multi-agent approval and orchestration."""

from teaagent.coordination.approval_backend import (
    ApprovalCoordinationBackend,
    FileBackedApprovalBackend,
    RemoteApprovalCoordinationBackend,
    resolve_approval_backend,
)

__all__ = [
    'ApprovalCoordinationBackend',
    'FileBackedApprovalBackend',
    'RemoteApprovalCoordinationBackend',
    'resolve_approval_backend',
]
