"""Permission modes and approval policy enforcement."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from teaagent.approval.manager import (
    ApprovalManager,
    JITApprovalState,
    MultiSigQuorumConfig,
    PermissionMode,
    _normalize_shell_arg,
)
from teaagent.approval.manager import (
    _verify_ssh_signature as _verify_ssh_signature,  # re-export: tests import it from teaagent.policy
)

if TYPE_CHECKING:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

logger = logging.getLogger(__name__)


# Re-export for backward compatibility
# JITApprovalState, MultiSigQuorumConfig, PermissionMode are imported from approval.manager.
# The multi-sig and high-risk helpers that used to live here are archived (A-P1-7).


@dataclass(frozen=True)
class ApprovalPolicy:
    """Session-scoped approval policy for high-risk tool calls.

    This class now delegates to ApprovalManager for unified approval coordination.
    Maintained for backward compatibility.
    """

    # Backward-compatible inert field for removed ``--approve-call-id`` preapproval.
    # Live one-call approval is JIT state, not this pre-run field.
    preapproved_call_ids: frozenset[str] = field(default_factory=frozenset)
    # CLI ``--approve-scoped`` — preapproved payload digests (tool+args hash)
    preapproved_payload_digests: frozenset[str] = field(default_factory=frozenset)
    allow_all_destructive: bool = False
    # Explicit full-access gate (P0-TR-001): ``allow_all_destructive`` only
    # matters when the session has already been promoted to danger-full-access.
    # Retained for backward-compatible caller metadata.
    full_access_acknowledged: bool = False
    permission_mode: PermissionMode = PermissionMode.PROMPT
    approval_store: ApprovalPresetStore | None = None
    approval_origin_run_id: str | None = (
        None  # Original run_id for scoped approval checking
    )
    enable_jit_prompt: bool = True  # Enable interactive TTY prompts for JIT approval
    multi_sig_config: MultiSigQuorumConfig = field(default_factory=MultiSigQuorumConfig)
    agent_id: str = ''  # Agent ID for multi-sig quorum identification
    workspace_root: str = '.'  # Workspace root for sync operations
    extra_path_keys: set[str] | None = None
    tenant_id: str = 'default'
    # Optional duck-typed AuditLogger; when set, governance fallbacks
    # (e.g. multisig_fallback) are written to the audit chain (G-P1-3).
    audit: Any | None = None
    _approval_manager: ApprovalManager = field(init=False, repr=False)

    def __post_init__(self) -> None:
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
                full_access_acknowledged=self.full_access_acknowledged,
                preapproved_call_ids=self.preapproved_call_ids,
                preapproved_payload_digests=self.preapproved_payload_digests,
                extra_path_keys=self.extra_path_keys,
                tenant_id=self.tenant_id,
                audit=self.audit,
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
        external_effect: bool = False,
    ) -> None:
        # Sync external JIT state with manager's state
        if jit_state:
            manager_state = self._approval_manager.get_jit_state()
            manager_state.approved_call_ids.update(jit_state.approved_call_ids)
            manager_state.session_approved_tools.update(
                jit_state.session_approved_tools
            )
            if hasattr(jit_state, 'once_grants') and hasattr(
                manager_state, 'once_grants'
            ):
                manager_state.once_grants.update(jit_state.once_grants)

        with self._flock_store():
            self._approval_manager.assert_allowed(
                tool_name=tool_name,
                call_id=call_id,
                destructive=destructive,
                arguments=arguments,
                plan_contract=plan_contract,
                read_only=read_only,
                description=description,
                handler=handler,
                external_effect=external_effect,
            )

        # Sync back JIT state in case it was modified by JIT prompting
        if jit_state:
            manager_state = self._approval_manager.get_jit_state()
            jit_state.approved_call_ids.update(manager_state.approved_call_ids)
            jit_state.session_approved_tools.update(
                manager_state.session_approved_tools
            )
            if hasattr(manager_state, 'once_grants'):
                if not hasattr(jit_state, 'once_grants'):
                    jit_state.once_grants = {}
                jit_state.once_grants.update(manager_state.once_grants)
                for consumed in (
                    set(jit_state.approved_call_ids) - manager_state.approved_call_ids
                ):
                    jit_state.approved_call_ids.discard(consumed)
                    jit_state.once_grants.pop(consumed, None)

    @staticmethod
    def _normalize_shell_arg(command: str) -> str:
        """Normalize a shell command string through multiple passes to defeat obfuscation."""
        return _normalize_shell_arg(command)

    @staticmethod
    def _compute_payload_digest(
        tool_name: str,
        call_id: str,
        arguments: dict[str, Any] | None,
    ) -> str:
        canonical = json.dumps(
            {
                'tool_name': tool_name,
                'call_id': call_id,
                'arguments': arguments or {},
            },
            sort_keys=True,
            separators=(',', ':'),
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @contextmanager
    def _flock_store(self) -> Iterator[None]:
        if not self.approval_store:
            yield
            return
        store_path = self.approval_store.path
        lock_path = store_path.with_suffix(store_path.suffix + '.flock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(lock_path, 'a+', encoding='utf-8')  # noqa: SIM115 — need raw fd for flock
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            fd.close()


def compute_scoped_payload_digest(
    tool_name: str, arguments: dict[str, Any] | None
) -> str:
    """Compute a scoped approval digest from tool name and arguments.

    This digest includes only the tool name and arguments (not call_id),
    allowing payload-based preapproval independent of model-controlled call IDs.

    Args:
        tool_name: Name of the tool being called.
        arguments: Arguments passed to the tool.

    Returns:
        SHA256 hex digest of the canonical payload JSON.
    """
    canonical = json.dumps(
        {'tool_name': tool_name, 'arguments': arguments or {}},
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def parse_permission_mode(value: str) -> PermissionMode:
    try:
        return PermissionMode(value)
    except ValueError as exc:
        allowed = ', '.join(mode.value for mode in PermissionMode)
        raise ValueError(
            f"unknown permission mode '{value}'. Available: {allowed}"
        ) from exc
