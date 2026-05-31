"""Unified ApprovalManager for coordinating all approval concerns.

This module provides a single entry point for all approval-related operations,
coordinating permission modes, JIT approvals, grants, scoped approvals, and
multi-sig quorum across the system.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import sys
import time
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


class PermissionModeEnforcer:
    """Enforces permission mode rules for tool calls (ADR-002)."""

    def __init__(
        self,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        allow_all_destructive: bool = False,
    ) -> None:
        self.permission_mode = permission_mode
        self.allow_all_destructive = allow_all_destructive

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
            return None

        return '__continue__'


class JITApprovalManager:
    """Manages JIT (Just-In-Time) approval state and TTY prompting (ADR-002)."""

    def __init__(self, enable_jit_prompt: bool = True) -> None:
        self.jit_state = JITApprovalState()
        self.enable_jit_prompt = enable_jit_prompt

    def is_approved(self, *, tool_name: str, call_id: str) -> bool:
        return self.jit_state.is_tool_session_approved(
            tool_name
        ) or self.jit_state.is_call_approved(call_id)

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
            self.jit_state.approve_once(call_id)
            return True
        if choice == 's':
            self.jit_state.approve_session(tool_name)
            return True
        if choice == 'd':
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' was denied by user."
            )
        if choice == 'e':
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' requires approval. "
                f'Tool: {tool_name}, Call ID: {call_id}, Arguments: {arguments}'
            )
        return None

    def _prompt(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None = None,
    ) -> str:
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


class MultiSigQuorumManager:
    """Manages multi-signature quorum for high-risk operations (ADR-002)."""

    def __init__(
        self,
        config: MultiSigQuorumConfig | None = None,
        agent_id: str = '',
    ) -> None:
        self.config = config or MultiSigQuorumConfig()
        self.agent_id = agent_id
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix='sig-collect'
        )

    def is_high_risk(self, tool_name: str, arguments: dict[str, Any] | None) -> bool:
        if not self.config.high_risk_patterns:
            return False
        tool_lower = tool_name.lower()
        for pattern in self.config.high_risk_patterns:
            if pattern.lower() in tool_lower:
                return True
        if arguments:
            # Lazy import to avoid circular dependency (policy.py imports from this module).
            from teaagent.policy import ApprovalPolicy  # type: ignore[import]

            for _key, value in arguments.items():
                if isinstance(value, str):
                    # Normalize the string value to defeat shell obfuscation before
                    # pattern matching — mirrors the normalization in
                    # ApprovalPolicy._is_high_risk_operation.
                    normalized_value = ApprovalPolicy._normalize_shell_arg(value)
                    raw_value = value.lower()
                    for pattern in self.config.high_risk_patterns:
                        pat_lower = pattern.lower()
                        if pat_lower in raw_value or pat_lower in normalized_value:
                            return True
        return False

    def check_quorum(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
    ) -> bool:
        """Check multi-signature quorum for high-risk operations.

        Returns:
            True if quorum is reached and operation is approved, False otherwise.
        """
        if not self.config.enabled:
            return False

        if not self.agent_id:
            print(
                '[Governance] Multi-Signature Quorum enabled but agent_id not set. '
                'Falling back to standard approval.'
            )
            return False

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

        print(
            f'[Governance] Multi-Signature Quorum is enabled. '
            f'Seeking {self.config.required_approvals} peer approvals...'
        )
        print(
            f'[Broadcast...] Sending JIT signature requests to peers '
            f'{self.config.peer_agent_ids}...'
        )

        signatures = self._collect_peer_signatures(request)

        if len(signatures) >= self.config.required_approvals:
            print(
                f'[✓] Quorum Reached '
                f'({len(signatures)}/{self.config.required_approvals} approvals).'
            )
            for sig in signatures:
                print(
                    f'[{sig.peer_id}]: SIGNED '
                    f'(SSH-Key-ID: {sig.ssh_key_id or "unknown"})'
                )
            return True
        else:
            print(
                f'[✗] Quorum Not Reached '
                f'({len(signatures)}/{self.config.required_approvals} required).'
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

        Integrates with federated_sync to broadcast the request via P2P sync,
        wait for peers to sign with their SSH keys, and verify signatures.
        """
        try:
            from teaagent.federated_sync import (
                ApprovalRequestMessage,
                FederatedGraphSync,
            )
        except ImportError:
            logger.warning('Federated sync not available for multi-sig quorum')
            return []

        sync = FederatedGraphSync(
            root=str(Path.cwd()),
            agent_id=self.agent_id or 'unknown',
        )

        submit_url = None
        local_relay = self.config.local_relay_base_url
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
            required_approvals=self.config.required_approvals,
            timeout_seconds=self.config.timeout_seconds,
            signature_submit_url=submit_url,
        )

        sync.broadcast_approval_request(
            approval_request,
            self.config.peer_agent_ids,
            peer_relay_urls=self.config.peer_relay_urls,
        )

        signature_messages = self._run_async_signature_collection(
            sync,
            request.request_id,
            required_approvals=self.config.required_approvals,
            relay_base_url=local_relay,
        )

        peer_signatures: list[PeerSignature] = []
        for sig_msg in signature_messages:
            message_to_verify = request.request_hash
            from teaagent.security_env import (
                allow_dev_signatures as env_allow_dev,
            )

            is_valid = _verify_ssh_signature(
                signature=sig_msg.signature,
                message=message_to_verify,
                ssh_key_id=sig_msg.peer_id,
                peer_public_keys=self.config.peer_public_keys,
                allow_dev_signatures=(
                    self.config.allow_dev_signatures or env_allow_dev()
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
          own event loop.
        - Otherwise, runs the coroutine via ``asyncio.run()``.
        """
        coro = sync.collect_approval_signatures(
            request_id,
            timeout_seconds=self.config.timeout_seconds,
            required_approvals=required_approvals,
            relay_base_url=relay_base_url,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():

            def _run_in_thread() -> Any:
                new_loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            timeout = self.config.timeout_seconds + 5
            future = self._executor.submit(_run_in_thread)
            return future.result(timeout=timeout)
        return asyncio.run(coro)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)


class ApprovalStoreManager:
    """Manages approval store presets and scoped approvals (ADR-002)."""

    def __init__(
        self,
        approval_store: ApprovalPresetStore | None = None,
        approval_origin_run_id: str | None = None,
    ) -> None:
        self.approval_store = approval_store
        self.approval_origin_run_id = approval_origin_run_id

    def check_preset(
        self,
        *,
        tool_name: str,
        permission_mode: str,
        arguments: dict[str, Any] | None = None,
    ) -> bool:
        if not self.approval_store:
            return False
        return self.approval_store.is_allowed(
            tool_name,
            permission_mode=permission_mode,
            arguments=arguments,
        )

    def check_scoped(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        if not self.approval_store or not self.approval_origin_run_id:
            return False
        return self.approval_store.try_consume_scoped_approval(
            run_id=self.approval_origin_run_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        )

    def handle_preapproved(
        self,
        *,
        call_id: str,
        preapproved_call_ids: frozenset[str],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        if (
            call_id not in preapproved_call_ids
            or not self.approval_store
            or not self.approval_origin_run_id
        ):
            return False
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
        return self.approval_store.try_consume_scoped_approval(
            run_id=self.approval_origin_run_id,
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        )


class ApprovalManager:
    """Unified manager composing PermissionModeEnforcer, JITApprovalManager,
    MultiSigQuorumManager, and ApprovalStoreManager (ADR-002).

    Maintains full backward compatibility — existing callers interact with
    this class exactly as before.
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

        self._permission_enforcer = PermissionModeEnforcer(
            permission_mode=permission_mode,
            allow_all_destructive=allow_all_destructive,
        )
        self._jit_manager = JITApprovalManager(enable_jit_prompt=enable_jit_prompt)
        self._multisig_manager = MultiSigQuorumManager(
            config=self.multi_sig_config, agent_id=agent_id
        )
        self._store_manager = ApprovalStoreManager(
            approval_store=approval_store,
            approval_origin_run_id=approval_origin_run_id,
        )

        self.jit_state = self._jit_manager.jit_state
        self._signature_executor = self._multisig_manager._executor

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
        mode_result = self._permission_enforcer.check(
            tool_name=tool_name,
            destructive=destructive,
            plan_contract=plan_contract,
            arguments=arguments,
            read_only=read_only,
            description=description,
            handler=handler,
        )
        if mode_result is None:
            return
        if mode_result != '__continue__':
            raise ToolPermissionError(mode_result)

        if self._jit_manager.is_approved(tool_name=tool_name, call_id=call_id):
            return

        if self._store_manager.check_preset(
            tool_name=tool_name,
            permission_mode=self.permission_mode.value,
            arguments=arguments,
        ):
            return

        if arguments is not None and self._store_manager.check_scoped(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        ):
            return

        if arguments is not None and self._store_manager.handle_preapproved(
            call_id=call_id,
            preapproved_call_ids=self.preapproved_call_ids,
            tool_name=tool_name,
            arguments=arguments,
        ):
            return

        if (
            self.multi_sig_config.enabled
            and self._multisig_manager.is_high_risk(tool_name, arguments)
            and self._multisig_manager.check_quorum(tool_name, call_id, arguments)
        ):
            return

        jit_result = self._jit_manager.prompt_and_resolve(
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments,
        )
        if jit_result is True:
            return

        raise ToolPermissionError(
            f"Tool call '{call_id}' for '{tool_name}' requires explicit approval."
        )

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
        self._multisig_manager.shutdown()


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
    'ApprovalStoreManager',
    'JITApprovalManager',
    'JITApprovalState',
    'MultiSigQuorumConfig',
    'MultiSigQuorumManager',
    'PeerSignature',
    'PermissionMode',
    'PermissionModeEnforcer',
    '_verify_ssh_signature',
]
