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
import os
import re
import shlex
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.read_only_gate import read_only_runtime_block_reason

if TYPE_CHECKING:
    from teaagent.approval_backend import ApprovalBackend as _ApprovalBackend
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protected skill directory patterns (DSK-P0-002)
# ---------------------------------------------------------------------------

_PROTECTED_SKILL_PATTERNS = (
    '.config/agent/skills',
    '.claude/skills',
    '.opencode/skill',
    '.opencode/skills',
)

_CANDIDATE_SKILL_PREFIX = '.teaagent/skill-candidates'


def is_protected_skill_path(workspace_root: Path, target_path: Path) -> bool:
    """Return True if *target_path* resides under a protected active-skill directory.

    Protected directories match one of the ``_PROTECTED_SKILL_PATTERNS``
    relative to *workspace_root*.  The candidate install path
    ``.teaagent/skill-candidates/`` is explicitly excluded so proposals
    continue to work.
    """
    try:
        relative = target_path.resolve().relative_to(workspace_root.resolve())
    except (ValueError, OSError):
        return False

    relative_str = str(relative)

    # Candidate path is always allowed.
    if (
        relative_str.startswith(_CANDIDATE_SKILL_PREFIX + '/')
        or relative_str == _CANDIDATE_SKILL_PREFIX
    ):
        return False

    for pattern in _PROTECTED_SKILL_PATTERNS:
        pattern_prefix = pattern + '/'
        if relative_str.startswith(pattern_prefix) or relative_str == pattern:
            return True

    return False


def _is_skill_dev_opt_in(workspace_root: str | Path) -> bool:
    """Check whether the skill-dev opt-in is active.

    Returns True when either the ``TEAAGENT_SKILL_DEV_OPT_IN`` environment
    variable is set to a truthy value, or the ``skill_dev_opt_in`` key is
    set to ``true`` in the workspace config (``.teaagent/config.json``).
    """
    env_val = os.environ.get('TEAAGENT_SKILL_DEV_OPT_IN')
    if env_val is not None:
        return env_val.strip().lower() in {'1', 'true', 'yes'}

    from teaagent.config_loader import load_workspace_config

    cfg = load_workspace_config(workspace_root)
    return bool(cfg.get('skill_dev_opt_in', False))


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


_JIT_APPROVAL_TIMEOUT_SECONDS: float = 60.0


class JITApprovalManager:
    """Manages JIT (Just-In-Time) approval state and TTY prompting (ADR-002)."""

    def __init__(
        self,
        enable_jit_prompt: bool = True,
        approval_timeout_seconds: float = _JIT_APPROVAL_TIMEOUT_SECONDS,
    ) -> None:
        self.jit_state = JITApprovalState()
        self.enable_jit_prompt = enable_jit_prompt
        self.approval_timeout_seconds = approval_timeout_seconds

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

        print(f'\n[TeaAgent] Permission required for tool: {tool_name}')
        print(f'[TeaAgent] Call ID: {call_id}')
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
            for _key, value in arguments.items():
                if isinstance(value, str):
                    # Normalize the string value to defeat shell obfuscation before
                    # pattern matching.
                    normalized_value = _normalize_shell_arg(value)
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

        request_id = hashlib.sha256(
            f'{self.agent_id}{call_id}{time.time()}'.encode()
        ).hexdigest()[:16]
        request_hash = self._generate_approval_hash(
            tool_name,
            call_id,
            arguments,
            request_id=request_id,
        )
        request = ApprovalRequest(
            request_id=request_id,
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
        request_id: str = '',
        run_id: str = '',
    ) -> str:
        """Generate cryptographic hash for approval request."""
        content = json.dumps(
            {
                'tool_name': tool_name,
                'call_id': call_id,
                'arguments': arguments or {},
                'run_id': run_id,
                'request_id': request_id,
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
            sig_age = abs(float(sig_msg.timestamp) - float(request.timestamp))
            if sig_age > float(self.config.timeout_seconds):
                print(
                    f'[Security] Rejected stale signature from peer {sig_msg.peer_id} '
                    f'(age={sig_age:.0f}s > timeout={self.config.timeout_seconds}s)'
                )
                continue
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
            from teaagent.async_bridge import run_coroutine_sync

            timeout = self.config.timeout_seconds + 5
            return run_coroutine_sync(
                coro,
                executor=self._executor,
                timeout_seconds=timeout,
            )
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
        full_access_acknowledged: bool = False,
        preapproved_call_ids: frozenset[str] = frozenset(),
        extra_path_keys: set[str] | None = None,
        approval_backend: _ApprovalBackend | None = None,
        tenant_id: str = 'default',
    ) -> None:
        self.permission_mode = permission_mode
        self.tenant_id = tenant_id
        self.approval_store = approval_store
        self.approval_origin_run_id = approval_origin_run_id
        self.enable_jit_prompt = enable_jit_prompt
        self.multi_sig_config = multi_sig_config or MultiSigQuorumConfig()
        self.agent_id = agent_id
        self.workspace_root = workspace_root
        self.allow_all_destructive = allow_all_destructive
        self.full_access_acknowledged = full_access_acknowledged
        self.preapproved_call_ids = preapproved_call_ids
        self._extra_path_keys: set[str] = extra_path_keys or set()

        self._permission_enforcer = PermissionModeEnforcer(
            permission_mode=permission_mode,
            allow_all_destructive=allow_all_destructive,
            full_access_acknowledged=full_access_acknowledged,
        )

        if approval_backend is not None:
            self._approval_backend: _ApprovalBackend = approval_backend
        else:
            from teaagent.approval_backend import backend_from_mode

            self._approval_backend = backend_from_mode(permission_mode)
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

    def assert_allowed(  # noqa: C901
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
        if arguments and isinstance(arguments, dict):
            self._assert_tenant_paths_match(tool_name, arguments)

        from teaagent.approval_backend import ApprovalRequest as _BeApprovalRequest

        backend_request = _BeApprovalRequest(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments or {},
            reason=(
                'destructive tool requires approval'
                if destructive
                else 'non-destructive tool call'
            ),
            annotations={
                'destructive': destructive,
                'read_only': read_only or False,
            },
            permission_mode=self.permission_mode,
            plan_contract=plan_contract,
            read_only=read_only,
            description=description,
            handler=handler,
            allow_all_destructive=self.allow_all_destructive,
            full_access_acknowledged=self.full_access_acknowledged,
        )

        decision = self._approval_backend.approve(backend_request)

        # P0-D-001: Validate tool path arguments are within workspace root.
        # Run before the early-return for ALLOW/DANGER_FULL_ACCESS so that
        # root containment is enforced regardless of permission mode.
        if destructive and arguments and isinstance(arguments, dict):
            self._assert_paths_in_workspace(tool_name, call_id, arguments)
            # DSK-P0-002: Block writes to active skill directories unless
            # the dev opt-in is active.
            self._assert_skill_path_not_protected(tool_name, call_id, arguments)

        if decision.approved:
            return
        if decision.reason_code != 'jit_required':
            # Map the backend reason code to a DenialReasonCode.
            dc = decision.reason_code
            if dc == DenialReasonCode.READ_ONLY_MODE.value:
                reason_code = DenialReasonCode.READ_ONLY_MODE
            elif dc == DenialReasonCode.WORKSPACE_WRITE_MODE.value:
                reason_code = DenialReasonCode.WORKSPACE_WRITE_MODE
            elif dc == DenialReasonCode.PLAN_CONTRACT_DENIED.value:
                reason_code = DenialReasonCode.PLAN_CONTRACT_DENIED
            elif dc == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED.value:
                reason_code = DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED
            else:
                reason_code = DenialReasonCode.MISSING_STATE
            logger.info(
                'tool_permission_denied: %s',
                tool_name,
                extra={
                    'event': 'tool_permission_denied',
                    'tool_name': tool_name,
                    'call_id': call_id,
                    'error_code': reason_code.value,
                },
            )
            raise ToolPermissionError(
                decision.reason or 'denied by approval backend',
                reason_code=reason_code,
            )

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

        if self.preapproved_call_ids:
            import os

            if os.environ.get(
                'TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS', ''
            ).strip().lower() in {
                '1',
                'true',
                'yes',
                'on',
            }:
                raise ToolPermissionError(
                    'preapproved_call_ids are disabled; use scoped approvals '
                    'with argument digests instead.',
                    reason_code=DenialReasonCode.MISSING_STATE,
                )

        if arguments is not None and self._store_manager.handle_preapproved(
            call_id=call_id,
            preapproved_call_ids=self.preapproved_call_ids,
            tool_name=tool_name,
            arguments=arguments,
        ):
            return

        # Track whether multi-sig was attempted but failed so we can report
        # the appropriate reason code.
        multisig_attempted = (
            self.multi_sig_config.enabled
            and self._multisig_manager.is_high_risk(tool_name, arguments)
        )
        if multisig_attempted and self._multisig_manager.check_quorum(
            tool_name, call_id, arguments
        ):
            return

        jit_result = self._jit_manager.prompt_and_resolve(
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments,
        )
        if jit_result is True:
            return

        # If multi-sig was attempted and fell through, report quorum failure.
        reason_code = (
            DenialReasonCode.MULTISIG_NO_QUORUM
            if multisig_attempted
            else DenialReasonCode.JIT_NO_APPROVAL
        )
        raise ToolPermissionError(
            f"Tool call '{call_id}' for '{tool_name}' requires explicit approval.",
            reason_code=reason_code,
        )

    # Path argument keys checked for workspace containment.
    _PATH_ARGUMENT_KEYS: tuple[str, ...] = ('path', 'file_path', 'target_path', 'file')

    def _assert_tenant_paths_match(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """Enforce that runs under a tenant cannot access files/paths belonging to other tenants."""
        values = []

        def collect_values(val: Any) -> None:
            if isinstance(val, (str, Path)):
                values.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    collect_values(v)
            elif isinstance(val, (list, tuple, set)):
                for v in val:
                    collect_values(v)

        collect_values(arguments)

        for val in values:
            val_str = str(val)
            try:
                resolved_val = Path(val_str).resolve()
            except Exception:
                continue

            parts = resolved_val.parts

            # Determine the path's owner tenant (if any)
            owner_tenant = None
            if 'tenants' in parts:
                idx = parts.index('tenants')
                if idx + 1 < len(parts):
                    owner_tenant = parts[idx + 1]
            else:
                if '.teaagent' in parts:
                    idx = parts.index('.teaagent')
                    if idx + 1 < len(parts):
                        sub = parts[idx + 1]
                        if sub in (
                            'runs',
                            'undo',
                            'background',
                            'run-keys',
                            'audit-encryption',
                        ):
                            owner_tenant = 'default'

            if owner_tenant is not None and owner_tenant != self.tenant_id:
                raise ToolPermissionError(
                    f"Tenant mismatch: Tool '{tool_name}' target path '{val_str}' "
                    f"belongs to tenant '{owner_tenant}', which does not match active tenant '{self.tenant_id}'.",
                    reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                )

    def _get_extended_path_keys(self) -> set[str]:
        """Return the full set of path argument keys (defaults + extensions)."""
        return set(self._PATH_ARGUMENT_KEYS) | self._extra_path_keys

    @staticmethod
    def _looks_like_path(value: Any) -> bool:
        """Return True if *value* heuristically looks like a filesystem path.

        A value is considered path-like when it is a ``Path`` object or a
        standalone string containing ``/`` or ``\\``.  Strings that contain
        spaces (e.g. shell commands like ``/usr/bin/python -m pytest``) are
        intentionally excluded — they are compound expressions, not single
        path arguments, and checking their entire body as one path would
        produce false positives.
        """
        if isinstance(value, Path):
            return True
        if isinstance(value, str) and value.strip():
            s = value.strip()
            if '/' in s or '\\' in s:
                return ' ' not in s
        return False

    def _assert_paths_in_workspace(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Check that tool path arguments stay within workspace_root.

        Two-phase check:
        1. Named path keys (default + extra_path_keys) are checked directly.
        2. ALL string/Path values are checked heuristically — any value
           containing ``/`` or ``\\`` (or that is a Path object) is validated
           for workspace containment.

        Raises ToolPermissionError if any path argument resolves outside
        the workspace root. This ensures explicit workspace root takes
        precedence over saved/imported state.
        """
        root_path = Path(self.workspace_root).resolve()
        key_set = self._get_extended_path_keys()

        for key, raw in arguments.items():
            if self._looks_like_path(raw):
                path_str = raw if isinstance(raw, str) else str(raw)
                try:
                    target = (root_path / path_str).resolve()
                    target.relative_to(root_path)
                except (ValueError, OSError):
                    raise ToolPermissionError(
                        f"Tool '{tool_name}' target path '{path_str}' is outside "
                        f"workspace root '{self.workspace_root}'. "
                        'Explicit workspace root must take precedence '
                        'over any saved state.',
                        reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                    ) from None
                continue

            if key not in key_set:
                continue
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                target = (root_path / raw).resolve()
                target.relative_to(root_path)
            except (ValueError, OSError):
                raise ToolPermissionError(
                    f"Tool '{tool_name}' target path '{raw}' is outside "
                    f"workspace root '{self.workspace_root}'. "
                    'Explicit workspace root must take precedence '
                    'over any saved state.',
                    reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
                ) from None

    def _assert_skill_path_not_protected(
        self,
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Raise ToolPermissionError when a write targets a protected skill directory.

        Does nothing when the skill-dev opt-in is active (env var or config).
        """
        if _is_skill_dev_opt_in(self.workspace_root):
            return

        root_path = Path(self.workspace_root).resolve()
        key_set = self._get_extended_path_keys()
        for key in key_set:
            raw = arguments.get(key)
            if not isinstance(raw, str) or not raw.strip():
                continue
            target = root_path / raw
            if is_protected_skill_path(root_path, target):
                raise ToolPermissionError(
                    f"Write to active skill directory '{raw}' is blocked. "
                    'Use the candidate install flow instead: skills are '
                    'managed through .teaagent/skill-candidates/. See docs '
                    'for --skill-dev-opt-in to bypass.',
                    reason_code=DenialReasonCode.SKILL_WRITE_BLOCKED,
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


def format_denial_message(
    error: ToolPermissionError,
    *,
    tool_name: str,
    call_id: str,
    permission_mode: str | None = None,
) -> str:
    """Produce a structured, actionable denial message for a blocked tool call.

    Generates remediation options based on the denial reason code so the
    user can immediately take corrective action.
    """
    reason_code = getattr(error, 'reason_code', None)
    mode = permission_mode or 'unknown'

    lines: list[str] = []
    lines.append(f'✗ Blocked: {tool_name}')
    lines.append(f'  Rule:    Permission mode = {mode}')
    lines.append(f'  Why:     {error}')
    lines.append('  Options:')

    idx = 1
    if reason_code in (
        DenialReasonCode.JIT_NO_APPROVAL,
        DenialReasonCode.MISSING_STATE,
    ):
        lines.append(
            f'    {idx}. Approve once:    teaagent approve --call-id {call_id}'
        )
        idx += 1
        lines.append(
            f'    {idx}. Approve session: teaagent approve --tool {tool_name} --session'
        )
        idx += 1

    if reason_code in (
        DenialReasonCode.READ_ONLY_MODE,
        DenialReasonCode.WORKSPACE_WRITE_MODE,
    ):
        lines.append(
            f'    {idx}. Change mode:     teaagent config set permission_mode prompt'
        )
        idx += 1

    lines.append(f'    {idx}. Learn more:      teaagent docs permissions')
    idx += 1
    lines.append(f'    {idx}. Approval status: teaagent approval check --root .')

    return '\n'.join(lines)


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

    # Extract subshell content from ORIGINAL command BEFORE $VAR stripping
    # (Pass 3/4).  This prevents Pass 0 from consuming e.g. $rm from
    # $(rm -rf /prod), which would lose the dangerous verb.
    backtick_contents = re.findall(r'`([^`]*)`', command)
    dollar_contents = re.findall(r'\$\(([^)]*)\)', command)
    process_sub_contents = re.findall(r'<\(([^)]*)\)', command)

    # Pass 0: Strip shell environment variable references
    # $VAR or ${VAR} -> '' (shell evaluates unset vars as empty)
    # Must run BEFORE quote stripping so $u'rod' -> 'rod' -> rod
    normalized = re.sub(r'\$\{[a-zA-Z_][a-zA-Z0-9_]*\}', '', normalized)
    normalized = re.sub(r'\$[a-zA-Z_][a-zA-Z0-9_]*', '', normalized)

    # Pass 1: Strip surrounding quotes from each token
    # "foo" -> foo, 'bar' -> bar
    normalized = re.sub(r"""(["'])(.*?)\1""", r'\2', normalized)

    # Pass 2: Remove backslash escapes: \r -> r, \" -> "
    normalized = re.sub(r'\\(.)', r'\1', normalized)

    # Pass 3/4 were moved before Pass 0 — extraction now happens above.

    # Pass 4b: Expand brace patterns like /pr{od,oduction} -> /prod /production
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
        # Collapse adjacent single-char flags: rm -r -f -> rm -rf
        collapsed: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith('-') and len(tok) == 2 and tok != '--':
                merged = tok
                i += 1
                while (
                    i < len(tokens)
                    and tokens[i].startswith('-')
                    and len(tokens[i]) == 2
                    and tokens[i] != '--'
                ):
                    merged += tokens[i][1:]
                    i += 1
                collapsed.append(merged)
            else:
                collapsed.append(tok)
                i += 1
        normalized = ' '.join(collapsed).lower()
    except ValueError:
        normalized = normalized.lower()

    # Combine: check the main normalized string PLUS any extracted subshell contents
    all_variants = [normalized]
    if brace_expanded != normalized:
        all_variants.append(brace_expanded.lower())
    for content in backtick_contents + dollar_contents + process_sub_contents:
        # Recursively normalize subshell contents to catch nested patterns
        all_variants.append(_normalize_shell_arg(content))

    return ' | '.join(all_variants)


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
    '_normalize_shell_arg',
    'format_denial_message',
    'is_protected_skill_path',
]
