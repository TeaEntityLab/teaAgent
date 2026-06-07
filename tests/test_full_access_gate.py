"""Full-access gate tests for P0-TR-001.

`allow_all_destructive` must be inert in non-full-access modes (notably
``prompt``). ``full_access_acknowledged=True`` records that a higher-level
caller performed the full-access ceremony, but it is not sufficient by itself:
the policy must be promoted to an explicit full-access permission mode. A
single innocuous boolean must never silently open a destructive bypass.

These tests cover the gate at three layers:
  1. ``PermissionModeEnforcer.check`` (pure unit, the chokepoint)
  2. ``ApprovalPolicy`` / ``ApprovalManager`` (integration through assert_allowed)
  3. ``AutoModeManager`` (the legitimate caller that opts in)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from teaagent.approval_manager import (
    ApprovalManager,
    PermissionMode,
    PermissionModeEnforcer,
)
from teaagent.auto_mode import AutoModeConfig
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.policy import ApprovalPolicy
from teaagent.runner._auto_mode_manager import AutoModeManager

_DESTRUCTIVE_TOOL = 'workspace_write_file'


def _check(
    *,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
    allow_all_destructive: bool = False,
    full_access_acknowledged: bool = False,
    destructive: bool = True,
    tool_name: str = _DESTRUCTIVE_TOOL,
):
    enforcer = PermissionModeEnforcer(
        permission_mode=permission_mode,
        allow_all_destructive=allow_all_destructive,
        full_access_acknowledged=full_access_acknowledged,
    )
    return enforcer.check(tool_name=tool_name, destructive=destructive)


# --------------------------------------------------------------------------
# Layer 1: PermissionModeEnforcer.check matrix
# --------------------------------------------------------------------------


class TestEnforcerGate:
    def test_prompt_allow_all_without_ack_blocks(self) -> None:
        result = _check(allow_all_destructive=True, full_access_acknowledged=False)
        assert result not in (None, '__continue__')
        assert 'full-access' in result.lower()

    def test_prompt_allow_all_with_ack_still_blocks(self) -> None:
        result = _check(allow_all_destructive=True, full_access_acknowledged=True)
        assert result not in (None, '__continue__')
        assert 'danger-full-access' in result.lower()

    def test_prompt_no_allow_all_falls_through_to_approval(self) -> None:
        # No bypass requested -> normal approval flow (sentinel continue).
        result = _check(allow_all_destructive=False, full_access_acknowledged=False)
        assert result == '__continue__'

    def test_ack_alone_is_not_sufficient(self) -> None:
        # Acknowledgment without allow_all_destructive must NOT bypass; it still
        # routes to the normal approval flow.
        result = _check(allow_all_destructive=False, full_access_acknowledged=True)
        assert result == '__continue__'

    def test_non_destructive_always_allowed(self) -> None:
        # Non-destructive calls are never gated, regardless of the flags.
        assert (
            _check(
                allow_all_destructive=True,
                full_access_acknowledged=False,
                destructive=False,
            )
            is None
        )

    @pytest.mark.parametrize(
        'mode',
        [PermissionMode.ALLOW, PermissionMode.DANGER_FULL_ACCESS],
    )
    def test_full_access_modes_bypass_without_ack(self, mode: PermissionMode) -> None:
        # ALLOW / DANGER_FULL_ACCESS are themselves explicit full-access modes;
        # they bypass at the mode level and never reach the ack gate.
        assert _check(permission_mode=mode, allow_all_destructive=False) is None
        assert (
            _check(
                permission_mode=mode,
                allow_all_destructive=True,
                full_access_acknowledged=False,
            )
            is None
        )

    def test_read_only_mode_blocks_destructive(self) -> None:
        result = _check(
            permission_mode=PermissionMode.READ_ONLY,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        )
        assert result not in (None, '__continue__')

    def test_workspace_write_unaffected_by_gate(self) -> None:
        # workspace_write_file is allowed in workspace-write mode irrespective
        # of the full-access gate.
        result = _check(
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            allow_all_destructive=False,
            full_access_acknowledged=False,
        )
        assert result is None


# --------------------------------------------------------------------------
# Layer 2: ApprovalPolicy / ApprovalManager integration
# --------------------------------------------------------------------------


class TestPolicyGate:
    def test_default_policy_does_not_acknowledge_full_access(self) -> None:
        assert ApprovalPolicy().full_access_acknowledged is False

    def test_full_access_acknowledged_is_immutable(self) -> None:
        policy = ApprovalPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.full_access_acknowledged = True

    def test_allow_all_without_ack_raises_with_reason_code(self) -> None:
        policy = ApprovalPolicy(allow_all_destructive=True)
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
            )
        assert ctx.value.reason_code == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED

    def test_allow_all_with_ack_still_blocks_without_full_access_mode(self) -> None:
        policy = ApprovalPolicy(
            allow_all_destructive=True, full_access_acknowledged=True
        )
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
            )
        assert ctx.value.reason_code == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED

    def test_ack_alone_still_requires_approval(self) -> None:
        # full_access_acknowledged without allow_all_destructive does not
        # auto-approve; it falls through to the (unmet) JIT approval path.
        policy = ApprovalPolicy(full_access_acknowledged=True)
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
            )
        assert ctx.value.reason_code == DenialReasonCode.JIT_NO_APPROVAL

    def test_non_destructive_unaffected(self) -> None:
        policy = ApprovalPolicy(allow_all_destructive=True)
        policy.assert_allowed(
            tool_name='workspace_read_file', call_id='c1', destructive=False
        )

    def test_manager_threads_ack_through(self) -> None:
        blocked = ApprovalManager(allow_all_destructive=True)
        with pytest.raises(ToolPermissionError) as ctx:
            blocked.assert_allowed(
                tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
            )
        assert ctx.value.reason_code == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED

        allowed = ApprovalManager(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        )
        allowed.assert_allowed(
            tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
        )


# --------------------------------------------------------------------------
# Layer 3: AutoModeManager opts in explicitly
# --------------------------------------------------------------------------


class TestAutoModeGate:
    def test_auto_mode_policy_acknowledges_full_access(self) -> None:
        manager = AutoModeManager(auto_mode_config=AutoModeConfig(enabled=True))
        policy = manager.get_auto_approve_policy()
        assert policy is not None
        assert policy.permission_mode is PermissionMode.DANGER_FULL_ACCESS
        assert policy.allow_all_destructive is True
        assert policy.full_access_acknowledged is True

    def test_auto_mode_policy_allows_destructive(self) -> None:
        manager = AutoModeManager(auto_mode_config=AutoModeConfig(enabled=True))
        policy = manager.get_auto_approve_policy()
        assert policy is not None
        policy.assert_allowed(
            tool_name=_DESTRUCTIVE_TOOL, call_id='c1', destructive=True
        )

    def test_disabled_auto_mode_returns_no_policy(self) -> None:
        manager = AutoModeManager(auto_mode_config=None)
        assert manager.get_auto_approve_policy() is None
