from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import re
import shlex
import sys
import time
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


@dataclass(frozen=True)
class MultiSigQuorumConfig:
    """Configuration for multi-signature quorum governance."""

    enabled: bool = False
    required_approvals: int = 2  # Number of peer signatures required
    peer_agent_ids: list[str] = field(default_factory=list)  # Known peer agent IDs
    peer_public_keys: dict[str, str] = field(
        default_factory=dict
    )  # Mapping of peer_id to SSH public key
    peer_relay_urls: dict[str, str] = field(
        default_factory=dict
    )  # peer_id -> signature relay base URL (WAN)
    local_relay_base_url: str | None = None  # Collect signatures via HTTP GET
    allow_dev_signatures: bool = False  # Dev-hash quorum signatures (non-production)
    high_risk_patterns: list[str] = field(
        default_factory=list
    )  # Patterns triggering multi-sig
    timeout_seconds: int = 300  # Timeout for collecting signatures

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


class PermissionMode(str, Enum):
    READ_ONLY = 'read-only'
    WORKSPACE_WRITE = 'workspace-write'
    PROMPT = 'prompt'
    ALLOW = 'allow'
    DANGER_FULL_ACCESS = 'danger-full-access'


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls."""

    # CLI/TUI ``--approve-call-id`` / ``approve <call_id>`` — binds scoped approval at execute time.
    preapproved_call_ids: frozenset[str] = field(default_factory=frozenset)
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
    _signature_executor: concurrent.futures.ThreadPoolExecutor = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        # Frozen dataclass: bypass setattr guard for non-field attribute.
        object.__setattr__(
            self,
            '_signature_executor',
            concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix='sig-collect'
            ),
        )

    def assert_allowed(
        self,
        *,
        tool_name: str,
        call_id: str,
        destructive: bool,
        arguments: dict[str, Any] | None = None,
        jit_state: JITApprovalState | None = None,
        plan_contract: Any = None,  # PlanContract if available
        read_only: bool | None = None,
        description: str = '',
        handler: Any | None = None,
    ) -> None:
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
            and self.approval_store.try_consume_scoped_approval(
                run_id=self.approval_origin_run_id,
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
        ):
            return
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
        # Warn if multi-sig is enabled but SSH verification is not cryptographically enforced
        if self.multi_sig_config.enabled and not _SSH_VERIFICATION_IMPLEMENTED:
            warnings.warn(
                'Multi-sig quorum is enabled but SSH signature verification is not '
                'cryptographically enforced. Do not rely on multi-sig quorum for production security.',
                stacklevel=2,
            )

        # Check multi-sig quorum if enabled and this is a high-risk operation
        if (
            self.multi_sig_config.enabled
            and self._is_high_risk_operation(tool_name, arguments)
            and self._check_multi_sig_quorum(tool_name, call_id, arguments)
        ):
            return
            # If multi-sig fails, proceed to normal approval flow
        if self.enable_jit_prompt and sys.stdin.isatty() and jit_state:
            choice = self._prompt_jit_approval(tool_name, call_id, arguments)
            if choice == 'o':
                jit_state.approve_once(call_id)
                return
            if choice == 's':
                jit_state.approve_session(tool_name)
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

    @staticmethod
    def _normalize_shell_arg(command: str) -> str:
        """Normalize a shell command string through multiple passes to defeat obfuscation.

        Applies successive normalization to catch:
        - Quoted strings: rm -r"f" /prod -> rm -rf /prod
        - Backtick injection: `echo /prod` -> /prod
        - Subshell expansion: $(echo /prod) -> /prod
        - Escaped characters: r\\m -> rm
        - Double-encoded sequences
        """
        if not command:
            return command

        normalized = command

        # Pass 1: Strip surrounding quotes from each token
        # "foo" -> foo, 'bar' -> bar
        normalized = re.sub(r"""(["'])(.*?)\1""", r'\2', normalized)

        # Pass 2: Remove backslash escapes: \r -> r, \" -> "
        normalized = re.sub(r'\\(.)', r'\1', normalized)

        # Pass 3: Extract content from backtick subshells: `cmd` -> cmd
        backtick_contents = re.findall(r'`([^`]*)`', normalized)

        # Pass 4: Extract content from $() subshells
        dollar_contents = re.findall(r'\$\(([^)]*)\)', normalized)

        # Pass 4b: Extract content from process substitution <(...)
        process_sub_contents = re.findall(r'<\(([^)]*)\)', normalized)

        # Pass 4c: Expand brace patterns like /pr{od,oduction} -> /prod /production
        def _expand_braces(s: str) -> str:
            """Expand simple brace alternation: a{b,c}d -> abd acd"""
            match = re.search(r'\{([^{}]+)\}', s)
            if not match:
                return s
            prefix = s[: match.start()]
            suffix = s[match.end() :]
            alternatives = match.group(1).split(',')
            expanded = ' '.join(prefix + alt.strip() + suffix for alt in alternatives)
            # Recurse for nested braces (one level)
            return _expand_braces(expanded) if '{' in expanded else expanded

        brace_expanded = _expand_braces(normalized)

        # Pass 5: Try shlex split for final normalization
        try:
            tokens = shlex.split(normalized)
            normalized = ' '.join(tokens).lower()
        except ValueError:
            normalized = normalized.lower()

        # Combine: check the main normalized string PLUS any extracted subshell contents
        all_variants = [normalized]
        if brace_expanded != normalized:
            all_variants.append(brace_expanded.lower())
        for content in backtick_contents + dollar_contents + process_sub_contents:
            # Recursively normalize subshell contents (one level deep)
            all_variants.append(content.lower())

        return ' | '.join(all_variants)

    def _is_high_risk_operation(
        self, tool_name: str, arguments: dict[str, Any] | None
    ) -> bool:
        """Check if operation matches high-risk patterns triggering multi-sig quorum.

        Uses shell command parsing to normalize arguments and prevent bypass attempts
        via token splitting, escape sequences, or encoding tricks.
        """
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

        # Default high-risk patterns with shell normalization
        default_high_risk = ['/prod', '/production', 'database', 'delete', 'rm -rf']

        for pattern in default_high_risk:
            if pattern in tool_name.lower():
                return True
            if arguments:
                # Try to normalize shell commands to catch bypass attempts
                args_str = json.dumps(arguments, sort_keys=True).lower()

                # Check raw string first
                if pattern in args_str:
                    return True

                # Multi-pass normalization for command-like arguments
                if 'command' in arguments or 'cmd' in arguments:
                    command_arg = arguments.get('command') or arguments.get('cmd', '')
                    if isinstance(command_arg, str):
                        normalized_cmd = self._normalize_shell_arg(command_arg)
                        if pattern in normalized_cmd:
                            return True
                    elif isinstance(command_arg, list):
                        joined_cmd = ' '.join(str(item) for item in command_arg)
                        normalized_cmd = self._normalize_shell_arg(joined_cmd)
                        if pattern in normalized_cmd:
                            return True
                    else:
                        # Fallback: convert any other type to string and check
                        normalized_cmd = self._normalize_shell_arg(str(command_arg))
                        if pattern in normalized_cmd:
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
        self, tool_name: str, call_id: str, arguments: dict[str, Any] | None, *, run_id: str = ''
    ) -> str:
        """Generate cryptographic hash for approval request."""
        content = json.dumps(
            {
                'tool_name': tool_name,
                'call_id': call_id,
                'arguments': arguments or {},
                'run_id': run_id,
                'time_window': int(time.time() / 3600),
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
        submit_url = None
        local_relay = self.multi_sig_config.local_relay_base_url
        if local_relay:
            submit_url = f'{local_relay.rstrip("/")}/api/v1/approval-signatures'

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
            signature_submit_url=submit_url,
        )

        # Broadcast to configured peer agents
        sync.broadcast_approval_request(
            approval_request,
            self.multi_sig_config.peer_agent_ids,
            peer_relay_urls=self.multi_sig_config.peer_relay_urls,
        )

        # Collect signatures from peers — offload async to avoid event loop starvation
        signature_messages = self._run_async_signature_collection(
            sync,
            request.request_id,
            required_approvals=self.multi_sig_config.required_approvals,
            relay_base_url=local_relay,
        )

        # Convert signature messages to PeerSignature objects with verification
        peer_signatures = []
        for sig_msg in signature_messages:
            # Verify the signature before accepting it
            message_to_verify = request.request_hash
            from teaagent.security_env import allow_dev_signatures as env_allow_dev

            is_valid = _verify_ssh_signature(
                signature=sig_msg.signature,
                message=message_to_verify,
                ssh_key_id=sig_msg.peer_id,
                peer_public_keys=self.multi_sig_config.peer_public_keys,
                allow_dev_signatures=(
                    self.multi_sig_config.allow_dev_signatures or env_allow_dev()
                ),
            )

            if not is_valid:
                print(
                    f'[Security] Rejected invalid signature from peer {sig_msg.peer_id}'
                )
                continue

            peer_sig = PeerSignature(
                peer_id=sig_msg.peer_id,
                signature=sig_msg.signature,
                timestamp=sig_msg.timestamp,
                ssh_key_id=sig_msg.ssh_key_id,
            )
            peer_signatures.append(peer_sig)

        return peer_signatures

    def _run_async_signature_collection(
        self,
        sync: Any,
        request_id: str,
        *,
        required_approvals: int = 1,
        relay_base_url: str | None = None,
    ) -> Any:
        """Run async signature collection without starving the event loop.

        Detects whether an event loop is active and dispatches accordingly:
        - If called from a thread with a running event loop, offloads to a
          ThreadPoolExecutor so the coroutine runs in a fresh thread with its
          own event loop (avoids ``RuntimeError: Cannot run the event loop
          from within a running event loop``).
        - Otherwise, runs the coroutine via ``asyncio.run()``.
        """
        coro = sync.collect_approval_signatures(
            request_id,
            timeout_seconds=self.multi_sig_config.timeout_seconds,
            required_approvals=required_approvals,
            relay_base_url=relay_base_url,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # We are on the event loop thread — offload to a worker thread
            # that creates its own event loop to run the coroutine.
            def _run_in_thread() -> Any:
                new_loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            timeout = self.multi_sig_config.timeout_seconds + 5
            future = self._signature_executor.submit(_run_in_thread)
            return future.result(timeout=timeout)
        return asyncio.run(coro)


def parse_permission_mode(value: str) -> PermissionMode:
    try:
        return PermissionMode(value)
    except ValueError as exc:
        allowed = ', '.join(mode.value for mode in PermissionMode)
        raise ValueError(
            f"unknown permission mode '{value}'. Available: {allowed}"
        ) from exc
