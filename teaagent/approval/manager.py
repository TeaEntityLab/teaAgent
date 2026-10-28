"""Unified ApprovalManager for coordinating all approval concerns.

This module provides a single entry point for all approval-related operations,
coordinating permission modes, JIT approvals, grants, scoped approvals, and
multi-sig quorum across the system.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
import os
import re  # noqa: F401 - kept importable from this facade (dir() parity)
import shlex  # noqa: F401 - kept importable from this facade (dir() parity)
import sys  # noqa: F401 - kept importable from this facade (dir() parity)
import time
from dataclasses import dataclass, field
from enum import Enum  # noqa: F401 - kept importable from this facade (dir() parity)
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from teaagent.approval._denial_format import format_denial_message
from teaagent.approval._jit import (
    _JIT_APPROVAL_TIMEOUT_SECONDS,  # noqa: F401 - kept importable from this facade
    JITApprovalManager,
    JITApprovalState,
)
from teaagent.approval._permission_mode import PermissionMode, PermissionModeEnforcer
from teaagent.approval._preset_scope import ApprovalStoreManager
from teaagent.approval._shell_normalize import _normalize_shell_arg
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.read_only_gate import (
    read_only_runtime_block_reason,  # noqa: F401 - dir() parity
)

if TYPE_CHECKING:
    from teaagent.approval.backend import ApprovalBackend as _ApprovalBackend
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

# Preserve the established operator-facing logger name across the module move.
logger = logging.getLogger('teaagent.approval_manager')

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
    except ValueError:
        # Outside the workspace: not a protected skill directory.
        return False
    except OSError:
        # Fail closed (owner decision 2026-10-27, approval split-plan Q6, F5):
        # a path that cannot be resolved cannot be shown to be unprotected.
        return True

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
class PeerApprovalRequest:
    """Request for peer approval broadcast via P2P sync."""

    request_id: str
    tool_name: str
    call_id: str
    arguments: dict[str, Any]
    request_hash: str
    timestamp: float
    requester_agent_id: str
    signatures: list[PeerSignature] = field(default_factory=list)


# Deprecated alias (A-P1-8, owner decision Q4): the P2P request was renamed to
# PeerApprovalRequest because two other classes are also named ApprovalRequest
# (approval.backend and runner._types). This name is the same class object.
# Plain alias: this module has no module-level __getattr__ deprecation pattern.
ApprovalRequest = PeerApprovalRequest


class MultiSigQuorumManager:
    """Manages multi-signature quorum for high-risk operations (ADR-002)."""

    def __init__(
        self,
        config: MultiSigQuorumConfig | None = None,
        agent_id: str = '',
        *,
        audit: Any | None = None,
        origin_run_id: str = '',
    ) -> None:
        self.config = config or MultiSigQuorumConfig()
        self.agent_id = agent_id
        # Optional audit sink (duck-typed AuditLogger). When present, governance
        # fallbacks are written to the audit chain (G-P1-3) in addition to logs.
        self._audit = audit
        self._origin_run_id = origin_run_id
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix='sig-collect'
        )

    def _audit_event(self, event_type: str, **payload: Any) -> None:
        """Best-effort emit to the audit chain; never affects the gate decision."""
        if self._audit is None:
            return
        try:
            self._audit.record(event_type, self._origin_run_id or '', **payload)
        except Exception:  # pragma: no cover - audit must never break approval
            logger.warning('Failed to record %s audit event', event_type)

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
            logger.warning(
                'Multi-sig quorum not available: agent_id not set',
                extra={
                    'event': 'multisig_fallback',
                    'reason': 'agent_id_not_set',
                    'tool_name': tool_name,
                    'call_id': call_id,
                    'required_approvals': self.config.required_approvals,
                },
            )
            # G-P1-3: also record to the audit chain so the misconfiguration is
            # detectable after the fact, not only in process logs.
            self._audit_event(
                'multisig_fallback',
                reason='agent_id_not_set',
                tool_name=tool_name,
                call_id=call_id,
                required_approvals=self.config.required_approvals,
            )
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
        request = PeerApprovalRequest(
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
        """Generate the canonical approval-request hash (see _multisig_crypto)."""
        from teaagent.approval._multisig_crypto import generate_approval_hash

        return generate_approval_hash(
            tool_name, call_id, arguments, request_id=request_id, run_id=run_id
        )

    def _collect_peer_signatures(
        self, request: PeerApprovalRequest
    ) -> list[PeerSignature]:
        """Collect peer signatures for approval request.

        Integrates with federated_sync to broadcast the request via P2P sync,
        wait for peers to sign with their SSH keys, and verify signatures.
        """
        from teaagent.approval._multisig_crypto import resolve_allow_dev_signatures
        from teaagent.security_env import allow_dev_signatures as env_allow_dev

        # SEC-15: fail closed before any broadcast when dev-hash signatures
        # would be honored over a non-loopback relay (they bypass SSH auth).
        allow_dev = resolve_allow_dev_signatures(
            self.config, env_enabled=env_allow_dev()
        )

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
            is_valid = _verify_ssh_signature(
                signature=sig_msg.signature,
                message=message_to_verify,
                ssh_key_id=sig_msg.peer_id,
                peer_public_keys=self.config.peer_public_keys,
                allow_dev_signatures=allow_dev,
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
        preapproved_payload_digests: frozenset[str] = frozenset(),
        extra_path_keys: set[str] | None = None,
        approval_backend: _ApprovalBackend | None = None,
        tenant_id: str = 'default',
        audit: Any | None = None,
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
        self.preapproved_payload_digests = preapproved_payload_digests
        self._extra_path_keys: set[str] = extra_path_keys or set()

        self._permission_enforcer = PermissionModeEnforcer(
            permission_mode=permission_mode,
            allow_all_destructive=allow_all_destructive,
            full_access_acknowledged=full_access_acknowledged,
        )

        if approval_backend is not None:
            self._approval_backend: _ApprovalBackend = approval_backend
        else:
            from teaagent.approval.backend import backend_from_mode

            self._approval_backend = backend_from_mode(permission_mode)
        self._jit_manager = JITApprovalManager(
            enable_jit_prompt=enable_jit_prompt,
            approval_store=approval_store,
            permission_mode=permission_mode.value,
        )
        self._multisig_manager = MultiSigQuorumManager(
            config=self.multi_sig_config,
            agent_id=agent_id,
            audit=audit,
            origin_run_id=approval_origin_run_id or '',
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
        external_effect: bool = False,
    ) -> None:
        """Check if a tool call is allowed under current approval policy.

        Raises:
            ToolPermissionError: If the tool call is not allowed.
        """
        if arguments and isinstance(arguments, dict):
            self._assert_tenant_paths_match(tool_name, arguments)

        from teaagent.approval.backend import ApprovalRequest as _BeApprovalRequest

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
                'external_effect': external_effect,
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

        # Permission-mode denials (read-only, workspace-write, unacknowledged
        # full-access) are final; prompt mode continues to the grant/approval chain.
        if not decision.approved and decision.reason_code != 'jit_required':
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

        # A matched deny preset is terminal over every grant (owner decision
        # 2026-10-27, extending G-P1-4). It is checked before the session and
        # once allows below, so neither can override it, and before consume_once,
        # so a denied attempt leaves a once grant unconsumed.
        preset_decision = self._store_manager.check_preset(
            tool_name=tool_name,
            permission_mode=self.permission_mode.value,
            arguments=arguments,
        )
        if preset_decision == 'deny':
            raise ToolPermissionError(
                f"Tool call '{call_id}' for '{tool_name}' is denied by an approval preset.",
                reason_code=DenialReasonCode.POLICY_DENIED,
            )

        if self.jit_state.is_tool_session_approved(tool_name):
            return
        from teaagent.policy import compute_scoped_payload_digest

        payload_digest = compute_scoped_payload_digest(tool_name, arguments or {})
        if self.jit_state.consume_once(call_id, payload_digest):
            return

        if (
            preset_decision == 'allow'
            and self.approval_store
            and self.approval_store.is_allowed(
                tool_name,
                permission_mode=self.permission_mode.value,
                arguments=arguments,
            )
        ):
            return

        if decision.approved:
            return

        if arguments is not None and self._store_manager.check_scoped(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
        ):
            return

        if (
            arguments is not None
            and self.preapproved_payload_digests
            and self._store_manager.handle_payload_digest_preapproved(
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                preapproved_payload_digests=self.preapproved_payload_digests,
            )
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

    @staticmethod
    def _has_symlink_component(root: Path, relative: str) -> bool:
        """Return True if any component of *relative* (resolved against *root*) is a symlink."""
        try:
            current = root
            for part in Path(relative).parts:
                if part == '..':
                    current = current.parent
                    continue
                current = current / part
                if current.is_symlink():
                    return True
        except ValueError:
            return False
        except OSError:
            # Fail closed (owner decision 2026-10-27, approval split-plan Q6, F3):
            # a component whose symlink status cannot be read is treated as unsafe.
            return True
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
                # Containment is the primary boundary: check it first so paths
                # that resolve outside the workspace report "outside workspace
                # root" regardless of any symlink ancestor (e.g. system paths
                # like /etc on macOS, where /etc is itself a symlink). .resolve()
                # follows symlinks, so out-of-workspace symlink escapes are
                # still caught here. The symlink-component check below is then
                # defense-in-depth for paths that resolve *inside* the workspace.
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
                if self._has_symlink_component(root_path, path_str):
                    raise ToolPermissionError(
                        f"Tool '{tool_name}' target path '{path_str}' contains a symlink component. "
                        'Symlinks are not allowed in tool call paths.',
                        reason_code=DenialReasonCode.SYMLINK_BLOCKED,
                    )
                continue

            if key not in key_set:
                continue
            if not isinstance(raw, str) or not raw.strip():
                continue
            # Containment first (see note above), then symlink defense-in-depth.
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
            if self._has_symlink_component(root_path, raw):
                raise ToolPermissionError(
                    f"Tool '{tool_name}' target path '{raw}' contains a symlink component. "
                    'Symlinks are not allowed in tool call paths.',
                    reason_code=DenialReasonCode.SYMLINK_BLOCKED,
                )

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

    def approve_once(
        self,
        call_id: str,
        *,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        payload_digest: str | None = None,
    ) -> None:
        """Approve a single tool call (one-time use)."""
        digest = payload_digest
        if digest is None and tool_name is not None:
            from teaagent.policy import compute_scoped_payload_digest

            digest = compute_scoped_payload_digest(tool_name, arguments or {})
        self.jit_state.approve_once(call_id, payload_digest=digest)

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
    'PeerApprovalRequest',
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
