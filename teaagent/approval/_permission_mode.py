"""Permission-mode policy: the mode enum and the per-call mode enforcer.

Moved unchanged from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044).
The enum values (``read-only``, ``workspace-write``, ``prompt``, ``allow``,
``danger-full-access``) are not changed. ``teaagent.approval.manager`` re-exports
both names.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from teaagent.read_only_gate import read_only_runtime_block_reason


class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'


class PermissionModeEnforcer:
    """Enforces permission mode rules for tool calls (ADR-002)."""

    def __init__(
        self,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        allow_all_destructive: bool = False,
        full_access_acknowledged: bool = False,
    ) -> None:
        self.permission_mode = permission_mode
        self.allow_all_destructive = allow_all_destructive
        # ``allow_all_destructive`` is only honored after an explicit
        # promotion to danger-full-access (P0-TR-001). A single innocuous
        # boolean must never silently open a destructive bypass while nominally
        # in a non-full-access mode such as ``prompt``. The acknowledgement
        # flag is retained for compatibility with higher-level callers.
        self.full_access_acknowledged = full_access_acknowledged

    def check(
        self,
        *,
        tool_name: str,
        destructive: bool,
        plan_contract: Any = None,
        arguments: dict[str, Any] | None = None,
        read_only: bool | None = None,
        description: str = '',
        handler: Any | None = None,
    ) -> Optional[str]:
        """Return ``None`` if allowed, or a block-reason string."""
        if self.permission_mode == PermissionMode.READ_ONLY:
            return read_only_runtime_block_reason(
                tool_name=tool_name,
                description=description,
                read_only=read_only,
                destructive=destructive,
                handler=handler,
            )

        if not destructive:
            return None

        if self.permission_mode == PermissionMode.WORKSPACE_WRITE:
            if tool_name in {
                'workspace_write_file',
                'workspace_apply_patch',
                'workspace_edit_at_hash',
            }:
                if plan_contract and arguments:
                    file_path = (
                        arguments.get('path') if isinstance(arguments, dict) else None
                    )
                    if file_path and not plan_contract.allows_file_write(file_path):
                        return (
                            f"Tool '{tool_name}' targeting '{file_path}' is not in approved plan file targets. "
                            f'Plan: {plan_contract.rel_path}'
                        )
                return None
            return f"Tool '{tool_name}' requires prompt/allow/danger-full-access permission mode."

        if self.permission_mode in {
            PermissionMode.ALLOW,
            PermissionMode.DANGER_FULL_ACCESS,
        }:
            return None

        if destructive and self.allow_all_destructive:
            return (
                f"Tool '{tool_name}' is destructive and 'allow_all_destructive' is "
                'enabled, but it only takes effect in danger-full-access mode. '
                'Use --permission-mode danger-full-access to proceed.'
            )

        return '__continue__'
