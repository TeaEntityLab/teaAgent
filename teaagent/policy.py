from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from teaagent.errors import ToolPermissionError

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore


class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls."""

    approved_call_ids: frozenset[str] = field(default_factory=frozenset)
    allow_all_destructive: bool = False
    permission_mode: PermissionMode = PermissionMode.PROMPT
    approval_store: ApprovalPresetStore | None = None
    approval_origin_run_id: str | None = (
        None  # Original run_id for scoped approval checking
    )

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        if not destructive:
            return
        if self.permission_mode == PermissionMode.READ_ONLY:
            raise ToolPermissionError(
                f"Tool '{tool_name}' is blocked by read-only permission mode."
            )
        if self.permission_mode == PermissionMode.WORKSPACE_WRITE:
            if tool_name in {
                'workspace_write_file',
                'workspace_apply_patch',
                'workspace_edit_at_hash',
            }:
                return
            raise ToolPermissionError(
                f"Tool '{tool_name}' requires prompt/allow/danger-full-access permission mode."
            )
        if self.permission_mode in {
            PermissionMode.ALLOW,
            PermissionMode.DANGER_FULL_ACCESS,
        }:
            return
        if destructive and self.allow_all_destructive:
            return
        # Check approval store presets before requiring explicit approval
        if self.approval_store and self.approval_store.is_allowed(
            tool_name,
            permission_mode=self.permission_mode.value,
            arguments=arguments,
        ):
            return
        # Check scoped approval for exact tool call matching (run-scoped)
        if (
            self.approval_store
            and self.approval_origin_run_id
            and arguments is not None
        ):
            matching_record = self.approval_store.check_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
            if matching_record:
                # Consume the scoped approval after successful match (one-time use)
                self.approval_store.consume_scoped_approval(matching_record.record_id)
                return
        # Fallback to bare call_id check for explicit CLI --approve-call-id backward compatibility
        if destructive and call_id not in self.approved_call_ids:
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' requires explicit approval."
            )


def parse_permission_mode(value: str) -> PermissionMode:
    try:
        return PermissionMode(value)
    except ValueError as exc:
        allowed = ', '.join(mode.value for mode in PermissionMode)
        raise ValueError(
            f"unknown permission mode '{value}'. Available: {allowed}"
        ) from exc
