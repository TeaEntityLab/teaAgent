from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

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
    required_approvals: int = 2  # Number of peer signatures required
    peer_agent_ids: list[str] = field(default_factory=list)  # Known peer agent IDs
    high_risk_patterns: list[str] = field(
        default_factory=list
    )  # Patterns triggering multi-sig
    timeout_seconds: int = 300  # Timeout for collecting signatures


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
    multi_sig_config: MultiSigQuorumConfig = field(default_factory=MultiSigQuorumConfig)
    agent_id: str = ''  # Agent ID for multi-sig quorum identification
    workspace_root: str = '.'  # Workspace root for sync operations

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
        # Check multi-sig quorum if enabled and this is a high-risk operation
        if (self.multi_sig_config.enabled and self._is_high_risk_operation(tool_name, arguments)
                and self._check_multi_sig_quorum(tool_name, call_id, arguments)):
            return
            # If multi-sig fails, proceed to normal approval flow
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
        """Check if operation matches high-risk patterns triggering multi-sig quorum."""
        if not arguments:
            return False

        # Check against configured high-risk patterns
        for pattern in self.multi_sig_config.high_risk_patterns:
            if pattern in tool_name:
                return True
            # Check if pattern appears in arguments (e.g., file paths)
            args_str = json.dumps(arguments, sort_keys=True)
            if pattern in args_str:
                return True

        # Default high-risk patterns
        default_high_risk = ['/prod', '/production', 'database', 'delete', 'rm -rf']
        for pattern in default_high_risk:
            if pattern in tool_name.lower():
                return True
            if arguments:
                args_str = json.dumps(arguments, sort_keys=True).lower()
                if pattern in args_str:
                    return True

        return False

    def _check_multi_sig_quorum(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
    ) -> bool:
        """Check multi-signature quorum for high-risk operations.

        Returns:
            True if quorum is reached and operation is approved, False otherwise.
        """
        if not self.multi_sig_config.enabled:
            return False

        if not self.agent_id:
            print(
                '[Governance] Multi-Signature Quorum enabled but agent_id not set. Falling back to standard approval.'
            )
            return False

        # Create approval request
        request_hash = self._generate_approval_hash(tool_name, call_id, arguments)
        request = ApprovalRequest(
            request_id=hashlib.sha256(
                f'{self.agent_id}{call_id}{time.time()}'.encode()
            ).hexdigest()[:16],
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments or {},
            request_hash=request_hash,
            timestamp=time.time(),
            requester_agent_id=self.agent_id,
        )

        # Broadcast approval request to peers
        print(
            f'[Governance] Multi-Signature Quorum is enabled. Seeking {self.multi_sig_config.required_approvals} peer approvals...'
        )
        print(
            f'[Broadcast...] Sending JIT signature requests to peers {self.multi_sig_config.peer_agent_ids}...'
        )

        # In a real implementation, this would broadcast via teaagent sync
        # For now, we simulate the quorum check
        signatures = self._collect_peer_signatures(request)

        if len(signatures) >= self.multi_sig_config.required_approvals:
            print(
                f'[✓] Quorum Reached ({len(signatures)}/{self.multi_sig_config.required_approvals} approvals).'
            )
            for sig in signatures:
                print(
                    f'[{sig.peer_id}]: SIGNED (SSH-Key-ID: {sig.ssh_key_id or "unknown"})'
                )
            return True
        else:
            print(
                f'[✗] Quorum Not Reached ({len(signatures)}/{self.multi_sig_config.required_approvals} required).'
            )
            return False

    def _generate_approval_hash(
        self, tool_name: str, call_id: str, arguments: dict[str, Any] | None
    ) -> str:
        """Generate cryptographic hash for approval request."""
        content = json.dumps(
            {
                'tool_name': tool_name,
                'call_id': call_id,
                'arguments': arguments or {},
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def _collect_peer_signatures(self, request: ApprovalRequest) -> list[PeerSignature]:
        """Collect peer signatures for approval request.

        This integrates with federated_sync to:
        1. Broadcast the request via teaagent sync to peer agents
        2. Wait for peers to sign with their SSH keys
        3. Collect and verify signatures
        """
        from teaagent.federated_sync import (
            ApprovalRequestMessage,
            FederatedGraphSync,
        )

        # Initialize federated sync for P2P broadcast
        sync = FederatedGraphSync(
            root=self.workspace_root,
            agent_id=self.agent_id or 'unknown',
        )

        # Create approval request message for broadcast
        approval_request = ApprovalRequestMessage(
            request_id=request.request_id,
            tool_name=request.tool_name,
            call_id=request.call_id,
            arguments=request.arguments or {},
            request_hash=request.request_hash,
            timestamp=request.timestamp,
            requester_agent_id=request.requester_agent_id,
            required_approvals=self.multi_sig_config.required_approvals,
            timeout_seconds=self.multi_sig_config.timeout_seconds,
        )

        # Broadcast to configured peer agents
        sync.broadcast_approval_request(
            approval_request,
            self.multi_sig_config.peer_agent_ids,
        )

        # Collect signatures from peers
        signature_messages = sync.collect_approval_signatures(
            request.request_id,
            timeout_seconds=self.multi_sig_config.timeout_seconds,
        )

        # Convert signature messages to PeerSignature objects
        peer_signatures = []
        for sig_msg in signature_messages:
            peer_sig = PeerSignature(
                peer_id=sig_msg.peer_id,
                signature=sig_msg.signature,
                timestamp=sig_msg.timestamp,
                ssh_key_id=sig_msg.ssh_key_id,
            )
            peer_signatures.append(peer_sig)

        return peer_signatures


def parse_permission_mode(value: str) -> PermissionMode:
    try:
        return PermissionMode(value)
    except ValueError as exc:
        allowed = ', '.join(mode.value for mode in PermissionMode)
        raise ValueError(
            f"unknown permission mode '{value}'. Available: {allowed}"
        ) from exc
