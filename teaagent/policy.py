from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from teaagent.errors import ToolPermissionError

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore


@dataclass
class JITApprovalState:
    """Mutable state for JIT (Just-In-Time) permission approvals during a session."""

    approved_call_ids: set[str] = field(default_factory=set)
    session_approved_tools: set[str] = field(default_factory=set)

    def approve_once(self, call_id: str) -> None:
        """Approve a single tool call (one-time use)."""
        self.approved_call_ids.add(call_id)

    def approve_session(self, tool_name: str) -> None:
        """Approve a tool for the entire session."""
        self.session_approved_tools.add(tool_name)

    def is_call_approved(self, call_id: str) -> bool:
        """Check if a specific call ID is approved."""
        return call_id in self.approved_call_ids

    def is_tool_session_approved(self, tool_name: str) -> bool:
        """Check if a tool is approved for the session."""
        return tool_name in self.session_approved_tools


class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls."""

    # Deprecated: approved_call_ids is a legacy escape hatch kept for CLI argument/test compatibility.
    # New workflows must use run-scoped exact-match scoped_approvals.
    approved_call_ids: frozenset[str] = field(default_factory=frozenset)
    allow_all_destructive: bool = False
    permission_mode: PermissionMode = PermissionMode.PROMPT
    approval_store: ApprovalPresetStore | None = None
    approval_origin_run_id: str | None = (
        None  # Original run_id for scoped approval checking
    )
    enable_jit_prompt: bool = True  # Enable interactive TTY prompts for JIT approval

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any] | None = None,
        jit_state: JITApprovalState | None = None,
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
        # Check JIT state for session-approved tools
        if jit_state and jit_state.is_tool_session_approved(tool_name):
            return
        # Check JIT state for once-approved call IDs
        if jit_state and jit_state.is_call_approved(call_id):
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
        # Legacy Fallback: bare call_id check for explicit CLI --approve-call-id backward compatibility.
        # This fallback is deprecated and scheduled for future removal.
        if destructive and call_id not in self.approved_call_ids:
            # Try JIT interactive prompt if enabled and TTY is available
            if self.enable_jit_prompt and sys.stdin.isatty() and jit_state:
                choice = self._prompt_jit_approval(tool_name, call_id, arguments)
                if choice == 'o':  # Once - add to approved_call_ids
                    jit_state.approve_once(call_id)
                    return
                elif choice == 's':  # Session - add to session_approved_tools
                    jit_state.approve_session(tool_name)
                    return
                elif choice == 'd':  # Deny
                    raise ToolPermissionError(
                        f"Tool call '{call_id}' for '{tool_name}' was denied by user."
                    )
                elif choice == 'e':  # Explain
                    raise ToolPermissionError(
                        f"Tool call '{call_id}' for '{tool_name}' requires approval. "
                        f"Tool: {tool_name}, Call ID: {call_id}, Arguments: {arguments}"
                    )
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' requires explicit approval."
            )

    def _prompt_jit_approval(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        """Prompt user for JIT approval via TTY.

        Returns:
            User choice: 'o' (once), 's' (session), 'd' (deny), 'e' (explain)
        """
        print(f"\n[TeaAgent] Permission required for tool: {tool_name}")
        print(f"[TeaAgent] Call ID: {call_id}")
        if arguments:
            print(f"[TeaAgent] Arguments: {arguments}")
        print(f"[TeaAgent] Approve this tool call?")
        print(f"[TeaAgent]   [o] Once - approve this single call")
        print(f"[TeaAgent]   [s] Session - approve for entire session")
        print(f"[TeaAgent]   [d] Deny - block this call")
        print(f"[TeaAgent]   [e] Explain - show details and deny")

        while True:
            try:
                choice = input("[TeaAgent] Choice [o/s/d/e]: ").strip().lower()
                if choice in ('o', 's', 'd', 'e'):
                    return choice
                print("[TeaAgent] Invalid choice. Please enter o, s, d, or e.")
            except (EOFError, KeyboardInterrupt):
                print("\n[TeaAgent] Interrupted. Denying permission.")
                return 'd'


def parse_permission_mode(value: str) -> PermissionMode:
    try:
        return PermissionMode(value)
    except ValueError as exc:
        allowed = ', '.join(mode.value for mode in PermissionMode)
        raise ValueError(
            f"unknown permission mode '{value}'. Available: {allowed}"
        ) from exc
