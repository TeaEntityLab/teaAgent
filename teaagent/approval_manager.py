"""Unified ApprovalManager for coordinating all approval concerns.

This module provides a single entry point for all approval-related operations,
coordinating permission modes, JIT approvals, grants, scoped approvals, and
multi-sig quorum across the system.
"""

from __future__ import annotations

import concurrent.futures
import logging
import sys
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from teaagent.errors import ToolPermissionError
from teaagent.read_only_gate import read_only_runtime_block_reason

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

logger = logging.getLogger(__name__)


class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'


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


@dataclass(frozen=True)
class PeerSignature:
    """Cryptographic signature from a peer developer for multi-sig approval."""

    peer_id: str
    signature: str
    timestamp: float
    ssh_key_id: Optional[str] = None


@dataclass(frozen=True)
class MultiSigQuorumConfig:
    """Configuration for multi-signature quorum governance."""

    enabled: bool = False
    required_approvals: int = 2
    peer_agent_ids: list[str] = field(default_factory=list)
    peer_public_keys: dict[str, str] = field(default_factory=dict)
    peer_relay_urls: dict[str, str] = field(default_factory=dict)
    local_relay_base_url: str | None = None
    allow_dev_signatures: bool = False
    high_risk_patterns: list[str] = field(default_factory=list)
    timeout_seconds: int = 300

    @classmethod
    def from_workspace_config(cls, root: str | Path) -> MultiSigQuorumConfig:
        """Load ``multi_sig`` section from ``<root>/.teaagent/config.json``."""
        from teaagent.config_loader import load_workspace_config

        section = load_workspace_config(root).get('multi_sig')
        if not isinstance(section, dict):
            return cls()

        peer_ids = section.get('peer_agent_ids') or []
        if not isinstance(peer_ids, list):
            peer_ids = []

        patterns = section.get('high_risk_patterns') or []
        if not isinstance(patterns, list):
            patterns = []

        relay_urls = section.get('peer_relay_urls') or {}
        if not isinstance(relay_urls, dict):
            relay_urls = {}

        public_keys = section.get('peer_public_keys') or {}
        if not isinstance(public_keys, dict):
            public_keys = {}

        local_relay = section.get('local_relay_base_url')
        local_relay_url = str(local_relay).strip() if local_relay else None
        if local_relay_url == '':
            local_relay_url = None

        return cls(
            enabled=bool(section.get('enabled', False)),
            required_approvals=int(section.get('required_approvals', 2)),
            peer_agent_ids=[str(item) for item in peer_ids],
            peer_public_keys={str(k): str(v) for k, v in public_keys.items()},
            peer_relay_urls={str(k): str(v).rstrip('/') for k, v in relay_urls.items()},
            local_relay_base_url=local_relay_url,
            allow_dev_signatures=bool(section.get('allow_dev_signatures', False)),
            high_risk_patterns=[str(item) for item in patterns],
            timeout_seconds=int(section.get('timeout_seconds', 300)),
        )


@dataclass(frozen=True)
class ApprovalRequest:
    """Request for peer approval broadcast via P2P sync."""

    request_id: str
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    request_hash: str
    timestamp: float
    requester_agent_id: str
    signatures: list[PeerSignature] = field(default_factory=list)


class ApprovalManager:
    """Unified manager for all approval concerns.

    This class coordinates:
    - Permission mode enforcement
    - JIT (Just-In-Time) approvals
    - Preset grants and scoped approvals
    - Multi-sig quorum for high-risk operations
    - Approval store persistence

    It provides a single interface for the runner and subagents to check
    and manage approvals without needing to understand the internal
    distribution of concerns across multiple modules.
    """

    def __init__(
        self,
        *,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        approval_store: ApprovalPresetStore | None = None,
        approval_origin_run_id: str | None = None,
        enable_jit_prompt: bool = True,
        multi_sig_config: MultiSigQuorumConfig | None = None,
        agent_id: str = '',
        workspace_root: str = '.',
        allow_all_destructive: bool = False,
        preapproved_call_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.permission_mode = permission_mode
        self.approval_store = approval_store
        self.approval_origin_run_id = approval_origin_run_id
        self.enable_jit_prompt = enable_jit_prompt
        self.multi_sig_config = multi_sig_config or MultiSigQuorumConfig()
        self.agent_id = agent_id
        self.workspace_root = workspace_root
        self.allow_all_destructive = allow_all_destructive
        self.preapproved_call_ids = preapproved_call_ids
        self.jit_state = JITApprovalState()
        self._signature_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix='sig-collect'
        )

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any] | None = None,
        plan_contract: Any = None,
        read_only: bool | None = None,
        description: str = '',
        handler: Any | None = None,
    ) -> None:
        """Check if a tool call is allowed under current approval policy.

        Raises:
            ToolPermissionError: If the tool call is not allowed.
        """
        if self.permission_mode == PermissionMode.READ_ONLY:
            block_reason = read_only_runtime_block_reason(
                tool_name=tool_name,
                description=description,
                read_only=read_only,
                destructive=destructive,
                handler=handler,
            )
            if block_reason is not None:
                raise ToolPermissionError(block_reason)
            return

        if not destructive:
            return

        if self.permission_mode == PermissionMode.WORKSPACE_WRITE:
            if tool_name in {
                'workspace_write_file',
                'workspace_apply_patch',
                'workspace_edit_at_hash',
            }:
                # Check plan contract file target validation
                if plan_contract and arguments:
                    file_path = (
                        arguments.get('path') if isinstance(arguments, dict) else None
                    )
                    if file_path and not plan_contract.allows_file_write(file_path):
                        raise ToolPermissionError(
                            f"Tool '{tool_name}' targeting '{file_path}' is not in approved plan file targets. "
                            f'Plan: {plan_contract.rel_path}'
                        )
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
        if self.jit_state.is_tool_session_approved(tool_name):
            return

        # Check JIT state for once-approved call IDs
        if self.jit_state.is_call_approved(call_id):
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
            and self.approval_store.try_consume_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
        ):
            return

        # Handle preapproved call IDs with scoped approval creation
        if (
            call_id in self.preapproved_call_ids
            and self.approval_store
            and self.approval_origin_run_id
            and arguments is not None
        ):
            if (
                self.approval_store.check_scoped_approval(
                    run_id=self.approval_origin_run_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                )
                is None
            ):
                self.approval_store.add_scoped_approval(
                    run_id=self.approval_origin_run_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                )
            if self.approval_store.try_consume_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            ):
                return

        # Check multi-sig quorum if enabled and this is a high-risk operation
        if (
            self.multi_sig_config.enabled
            and self._is_high_risk_operation(tool_name, arguments)
            and self._check_multi_sig_quorum(tool_name, call_id, arguments)
        ):
            return

        # Prompt for JIT approval if enabled, TTY is available, and jit_state is present
        # Note: jit_state is always present in ApprovalManager (initialized in __init__)
        # The external caller passes jit_state to ApprovalPolicy which syncs it
        if self.enable_jit_prompt and sys.stdin.isatty():
            choice = self._prompt_jit_approval(tool_name, call_id, arguments)
            if choice == 'o':
                self.jit_state.approve_once(call_id)
                return
            if choice == 's':
                self.jit_state.approve_session(tool_name)
                return
            if choice == 'd':
                raise ToolPermissionError(
                    f"Tool call '{call_id}' for '{tool_name}' was denied by user."
                )
            if choice == 'e':
                raise ToolPermissionError(
                    f"Tool call '{call_id}' for '{tool_name}' requires approval. "
                    f'Tool: {tool_name}, Call ID: {call_id}, Arguments: {arguments}'
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
        print(f'\n[TeaAgent] Permission required for tool: {tool_name}')
        print(f'[TeaAgent] Call ID: {call_id}')
        if arguments:
            print(f'[TeaAgent] Arguments: {arguments}')
        print('[TeaAgent] Approve this tool call?')
        print('[TeaAgent]   [o] Once - approve this single call')
        print('[TeaAgent]   [s] Session - approve for entire session')
        print('[TeaAgent]   [d] Deny - block this call')
        print('[TeaAgent]   [e] Explain - show details and deny')

        while True:
            try:
                choice = input('[TeaAgent] Choice [o/s/d/e]: ').strip().lower()
                if choice in ('o', 's', 'd', 'e'):
                    return choice
                print('[TeaAgent] Invalid choice. Please enter o, s, d, or e.')
            except (EOFError, KeyboardInterrupt):
                print('\n[TeaAgent] Interrupted. Denying permission.')
                return 'd'

    def _is_high_risk_operation(
        self, tool_name: str, arguments: dict[str, Any] | None
    ) -> bool:
        """Check if this operation matches high-risk patterns for multi-sig."""
        if not self.multi_sig_config.high_risk_patterns:
            return False

        # Check tool name against patterns
        tool_lower = tool_name.lower()
        for pattern in self.multi_sig_config.high_risk_patterns:
            if pattern.lower() in tool_lower:
                return True

        # Check arguments for high-risk commands (e.g., shell commands)
        if arguments:
            for key, value in arguments.items():
                if isinstance(value, str):
                    for pattern in self.multi_sig_config.high_risk_patterns:
                        if pattern.lower() in value.lower():
                            return True

        return False

    def _check_multi_sig_quorum(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
    ) -> bool:
        """Check if multi-sig quorum is satisfied for this operation.

        Returns:
            True if quorum is satisfied, False otherwise.
        """
        # Placeholder for multi-sig quorum checking
        # This would integrate with the actual multi-sig implementation
        # For now, we return False to fall through to normal approval flow
        return False

    def approve_once(self, call_id: str) -> None:
        """Approve a single tool call (one-time use)."""
        self.jit_state.approve_once(call_id)

    def approve_session(self, tool_name: str) -> None:
        """Approve a tool for the entire session."""
        self.jit_state.approve_session(tool_name)

    def get_jit_state(self) -> JITApprovalState:
        """Get the current JIT approval state."""
        return self.jit_state

    def shutdown(self) -> None:
        """Clean up resources (thread pool, etc.)."""
        self._signature_executor.shutdown(wait=True)


# Sentinel: False until a real cryptography library is integrated.
_SSH_VERIFICATION_IMPLEMENTED = True


def _verify_ssh_signature(
    signature: str,
    message: str,
    ssh_key_id: Optional[str],
    peer_public_keys: dict[str, str],
    *,
    allow_dev_signatures: bool = False,
) -> bool:
    """Verify an SSH signature; dev-hash only when explicitly allowed."""
    import hashlib
    import secrets

    from teaagent.ssh_signatures import is_ssh_signature_blob, verify_message_ssh

    if not signature or not signature.strip():
        return False
    if not ssh_key_id or not ssh_key_id.strip():
        return False
    pubkey = peer_public_keys.get(ssh_key_id)
    if not pubkey:
        return False
    if is_ssh_signature_blob(signature):
        return verify_message_ssh(pubkey, message, signature)
    if not allow_dev_signatures:
        return False
    expected = hashlib.sha256((message + pubkey).encode()).hexdigest()
    return secrets.compare_digest(signature, expected)


__all__ = [
    'ApprovalManager',
    'ApprovalRequest',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'PeerSignature',
    'PermissionMode',
    '_verify_ssh_signature',
]
