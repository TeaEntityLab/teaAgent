"""Unified ApprovalManager for coordinating all approval concerns.

This module provides a single entry point for all approval-related operations,
coordinating permission modes, JIT approvals, grants, scoped approvals, and
multi-sig quorum across the system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
)

from teaagent.approval._denial_format import format_denial_message
from teaagent.approval._jit import (
    _JIT_APPROVAL_TIMEOUT_SECONDS as _JIT_APPROVAL_TIMEOUT_SECONDS,  # re-export
)
from teaagent.approval._jit import (
    JITApprovalManager,
    JITApprovalState,
)
from teaagent.approval._multisig import (
    _SSH_VERIFICATION_IMPLEMENTED as _SSH_VERIFICATION_IMPLEMENTED,  # re-export
)
from teaagent.approval._multisig import (
    ApprovalRequest,
    MultiSigQuorumConfig,
    MultiSigQuorumManager,
    PeerApprovalRequest,
    PeerSignature,
    _verify_ssh_signature,
)
from teaagent.approval._path_containment import _PathContainmentMixin
from teaagent.approval._permission_mode import PermissionMode, PermissionModeEnforcer
from teaagent.approval._preset_scope import ApprovalStoreManager
from teaagent.approval._shell_normalize import _normalize_shell_arg
from teaagent.approval._skill_protection import (
    _is_skill_dev_opt_in,
    is_protected_skill_path,
)
from teaagent.errors import DenialReasonCode, ToolPermissionError

if TYPE_CHECKING:
    from teaagent.approval.backend import ApprovalBackend as _ApprovalBackend
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

# Preserve the established operator-facing logger name across the module move.
logger = logging.getLogger('teaagent.approval_manager')

# ---------------------------------------------------------------------------
# Protected skill directory patterns (DSK-P0-002)
# ---------------------------------------------------------------------------


class ApprovalManager(_PathContainmentMixin):
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
