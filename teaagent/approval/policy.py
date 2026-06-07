"""Permission enforcement strategies (canonical import path)."""

from teaagent.approval_manager import PermissionModeEnforcer
from teaagent.policy import parse_permission_mode

__all__ = [
    'PermissionModeEnforcer',
    'parse_permission_mode',
]
