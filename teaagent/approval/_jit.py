"""JIT (just-in-time) approval grants and the interactive TTY prompt.

Moved unchanged from ``teaagent.approval.manager`` (A-P1-6 split, ADR-0044).
``teaagent.approval.manager`` re-exports all three names.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from teaagent.approval._permission_mode import PermissionMode
from teaagent.errors import DenialReasonCode, ToolPermissionError

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore


@dataclass
class JITApprovalState:
    """Mutable state for JIT (Just-In-Time) permission approvals during a session."""

    approved_call_ids: set[str] = field(default_factory=set)
    session_approved_tools: set[str] = field(default_factory=set)
    # call_id -> canonical payload digest. Missing entry means a legacy
    # call-id-only grant (still one-time, not payload-bound).
    once_grants: dict[str, str] = field(default_factory=dict)

    def approve_once(self, call_id: str, payload_digest: str | None = None) -> None:
        """Approve a single tool call (one-time use).

        When *payload_digest* is provided the grant is bound to that exact
        tool+arguments intent. A later consume with a different digest fails
        and leaves the grant intact.
        """
        self.approved_call_ids.add(call_id)
        if payload_digest is not None:
            self.once_grants[call_id] = payload_digest

    def approve_session(self, tool_name: str) -> None:
        """Approve a tool for the entire session."""
        self.session_approved_tools.add(tool_name)

    def is_call_approved(self, call_id: str, payload_digest: str | None = None) -> bool:
        """Peek whether a one-time grant exists (does not consume)."""
        if call_id not in self.approved_call_ids and call_id not in self.once_grants:
            return False
        stored = self.once_grants.get(call_id)
        return stored is None or payload_digest is None or stored == payload_digest

    def consume_once(self, call_id: str, payload_digest: str) -> bool:
        """Consume a one-time grant if it matches *payload_digest*.

        Digest-bound grants require an exact match. Legacy call-id-only grants
        are consumed on first use of any payload. Mismatched digest-bound grants
        are left in place so the authorized payload can still consume them.
        """
        if call_id not in self.approved_call_ids and call_id not in self.once_grants:
            return False
        stored = self.once_grants.get(call_id)
        if stored is not None and stored != payload_digest:
            return False
        self.approved_call_ids.discard(call_id)
        self.once_grants.pop(call_id, None)
        return True

    def is_tool_session_approved(self, tool_name: str) -> bool:
        """Check if a tool is approved for the session."""
        return tool_name in self.session_approved_tools


_JIT_APPROVAL_TIMEOUT_SECONDS: float = 60.0


class JITApprovalManager:
    """Manages JIT (Just-In-Time) approval state and TTY prompting (ADR-002)."""

    def __init__(
        self,
        enable_jit_prompt: bool = True,
        approval_timeout_seconds: float = _JIT_APPROVAL_TIMEOUT_SECONDS,
        approval_store: ApprovalPresetStore | None = None,
        permission_mode: str = PermissionMode.PROMPT.value,
    ) -> None:
        self.jit_state = JITApprovalState()
        self.enable_jit_prompt = enable_jit_prompt
        self.approval_timeout_seconds = approval_timeout_seconds
        self.approval_store = approval_store
        self.permission_mode = permission_mode

    def _deny_preset_matches(
        self, tool_name: str, arguments: dict[str, object] | None
    ) -> bool:
        """Return True when a deny preset blocks this tool call.

        Mirrors the deny check in ``ApprovalManager.assert_allowed`` (owner
        decision 2026-10-27: a deny preset is terminal over grants). With
        ``arguments=None`` the payload is unknown, so path- or command-scoped
        denies cannot be evaluated; the check fails closed and treats any deny
        grant recorded for the tool as a match.
        """
        if self.approval_store is None:
            return False
        if arguments is None:
            return any(
                grant.scope == 'deny' and grant.tool_name == tool_name
                for grant in self.approval_store.list_grants()
            )
        decision = self.approval_store.check(
            tool_name,
            permission_mode=self.permission_mode,
            arguments=arguments,
        )
        return decision.get('decision') == 'deny'

    def is_approved(
        self,
        *,
        tool_name: str,
        call_id: str,
        payload_digest: str | None = None,
        arguments: dict[str, object] | None = None,
    ) -> bool:
        """Peek whether a call is approved. Never consumes a once grant.

        A matched deny preset is checked first and wins over session and once
        grants, matching ``assert_allowed``.
        """
        if self._deny_preset_matches(tool_name, arguments):
            return False
        return self.jit_state.is_tool_session_approved(tool_name) or (
            self.jit_state.is_call_approved(call_id, payload_digest)
        )

    def prompt_and_resolve(
        self,
        *,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None = None,
    ) -> Optional[bool]:
        """Prompt via TTY. Returns True (approved), False (denied), None (no TTY)."""
        if not self.enable_jit_prompt or not sys.stdin.isatty():
            return None
        choice = self._prompt(tool_name, call_id, arguments)
        if choice == 'o':
            digest = None
            if arguments is not None:
                from teaagent.policy import compute_scoped_payload_digest

                digest = compute_scoped_payload_digest(tool_name, arguments)
            self.jit_state.approve_once(call_id, payload_digest=digest)
            return True
        if choice == 's':
            self.jit_state.approve_session(tool_name)
            return True
        if choice == 'd':
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' was denied by user.",
                reason_code=DenialReasonCode.JIT_USER_DENIED,
            )
        if choice == 'e':
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' requires approval.",
                reason_code=DenialReasonCode.JIT_USER_DENIED,
            )
        return None

    def _prompt(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        import threading

        from teaagent.governance.conversation_ux import format_approval_prompt_human

        json_mode = os.environ.get('TEAAGENT_JSON_APPROVALS', '').lower() in (
            '1',
            'true',
            'yes',
        )
        if json_mode:
            print(
                format_approval_prompt_human(
                    tool_name,
                    call_id,
                    arguments,
                    json_mode=True,
                )
            )
        else:
            print(
                '\n[TeaAgent] '
                + format_approval_prompt_human(tool_name, call_id, arguments)
            )
        if not json_mode:
            if arguments:
                print(f'[TeaAgent] Arguments: {arguments}')
            print('[TeaAgent] Approve this tool call?')
            print('[TeaAgent]   [o] Once - approve this single call')
            print('[TeaAgent]   [s] Session - approve for entire session')
            print('[TeaAgent]   [d] Deny - block this call')
            print('[TeaAgent]   [e] Explain - show details and deny')

        def _read_input(result_holder: list[str]) -> None:
            try:
                result_holder.append(
                    input('[TeaAgent] Choice [o/s/d/e]: ').strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                result_holder.append('__interrupt__')

        while True:
            result_holder: list[str] = []
            t = threading.Thread(target=_read_input, args=(result_holder,), daemon=True)
            t.start()
            t.join(self.approval_timeout_seconds)

            if not result_holder:
                print(
                    f'\n[TeaAgent] No response after {self.approval_timeout_seconds:.0f}s. '
                    'Denying permission.'
                )
                return 'd'

            choice = result_holder[0]
            if choice == '__interrupt__':
                print('\n[TeaAgent] Interrupted. Denying permission.')
                return 'd'
            if choice in ('o', 's', 'd', 'e'):
                return choice
            print('[TeaAgent] Invalid choice. Please enter o, s, d, or e.')
