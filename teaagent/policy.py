from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import re
import shlex
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from teaagent.approval_manager import (
    ApprovalManager,
    ApprovalRequest,
    JITApprovalState,
    MultiSigQuorumConfig,
    PeerSignature,
    PermissionMode,
    _verify_ssh_signature,
)

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

logger = logging.getLogger(__name__)


# Re-export for backward compatibility
# JITApprovalState, PeerSignature, MultiSigQuorumConfig, PermissionMode are now imported from approval_manager


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls.

    This class now delegates to ApprovalManager for unified approval coordination.
    Maintained for backward compatibility.
    """

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
    _approval_manager: ApprovalManager = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Frozen dataclass: bypass setattr guard for non-field attributes.
        object.__setattr__(
            self,
            '_signature_executor',
            concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix='sig-collect'
            ),
        )
        # Create ApprovalManager instance
        object.__setattr__(
            self,
            '_approval_manager',
            ApprovalManager(
                permission_mode=self.permission_mode,
                approval_store=self.approval_store,
                approval_origin_run_id=self.approval_origin_run_id,
                enable_jit_prompt=self.enable_jit_prompt,
                multi_sig_config=self.multi_sig_config,
                agent_id=self.agent_id,
                workspace_root=self.workspace_root,
                allow_all_destructive=self.allow_all_destructive,
                preapproved_call_ids=self.preapproved_call_ids,
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
        # Sync external JIT state with manager's state
        if jit_state:
            manager_state = self._approval_manager.get_jit_state()
            manager_state.approved_call_ids.update(jit_state.approved_call_ids)
            manager_state.session_approved_tools.update(
                jit_state.session_approved_tools
            )

        # Delegate to ApprovalManager
        self._approval_manager.assert_allowed(
            tool_name=tool_name,
            call_id=call_id,
            destructive=destructive,
            arguments=arguments,
            plan_contract=plan_contract,
            read_only=read_only,
            description=description,
            handler=handler,
        )

        # Sync back JIT state in case it was modified by JIT prompting
        if jit_state:
            manager_state = self._approval_manager.get_jit_state()
            jit_state.approved_call_ids.update(manager_state.approved_call_ids)
            jit_state.session_approved_tools.update(
                manager_state.session_approved_tools
            )

    # Note: Multi-sig quorum methods are kept here for backward compatibility
    # and complex federated_sync integration. They can be migrated to ApprovalManager
    # in a future iteration.

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
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
        *,
        run_id: str = '',
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
        try:
            from teaagent.federated_sync import (
                ApprovalRequestMessage,
                FederatedGraphSync,
            )
        except ImportError:
            # Federated sync not available - return empty list (no quorum)
            logger.warning('Federated sync not available for multi-sig quorum')
            return []

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
