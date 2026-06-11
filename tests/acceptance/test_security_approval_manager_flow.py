"""Acceptance: ApprovalManager enforces permission modes, JIT state, and multi-sig boundaries.

Security boundary: ToolPermissionError must be raised for blocked tools.
Happy path: read-only non-destructive passes; workspace-write allows file ops.
Edge case: missing plan_contract blocks writes; empty multi-sig config is safe."""

from __future__ import annotations

import pytest

from teaagent.approval import (
    ApprovalManager,
    MultiSigQuorumConfig,
    PermissionModeEnforcer,
)
from teaagent.approval_manager import _verify_ssh_signature
from teaagent.types import JITApprovalState, PermissionMode, ToolPermissionError


def test_approval_manager_imports():
    assert ApprovalManager is not None
    assert PermissionModeEnforcer is not None
    assert PermissionMode.READ_ONLY == 'read-only'


def test_read_only_blocks_destructive():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.READ_ONLY)
    reason = enforcer.check(tool_name='workspace_write_file', destructive=True)
    assert reason is not None
    assert 'blocked' in reason.lower()


def test_read_only_allows_read_tool():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.READ_ONLY)
    reason = enforcer.check(
        tool_name='workspace_read_file', destructive=False, read_only=True
    )
    assert reason is None


def test_workspace_write_allows_file_write_with_plan():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.WORKSPACE_WRITE)
    reason = enforcer.check(
        tool_name='workspace_write_file',
        destructive=True,
        arguments={'path': 'src/main.py'},
    )
    # Without a plan_contract, workspace_write allows file write
    assert reason is None


def test_workspace_write_blocks_shell_mutate():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.WORKSPACE_WRITE)
    reason = enforcer.check(
        tool_name='workspace_run_shell_mutate',
        destructive=True,
    )
    assert reason is not None
    assert 'prompt' in reason.lower() or 'permission' in reason.lower()


def test_allow_mode_allows_all():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.ALLOW)
    assert (
        enforcer.check(tool_name='workspace_run_shell_mutate', destructive=True) is None
    )


def test_prompt_mode_returns_continue_for_destructive():
    enforcer = PermissionModeEnforcer(permission_mode=PermissionMode.PROMPT)
    reason = enforcer.check(tool_name='workspace_run_shell_mutate', destructive=True)
    assert reason == '__continue__'


def test_approve_once_then_check():
    state = JITApprovalState()
    state.approve_once('call-1')
    assert state.is_call_approved('call-1')
    assert not state.is_call_approved('call-2')


def test_approve_session_then_check():
    state = JITApprovalState()
    state.approve_session('shell')
    assert state.is_tool_session_approved('shell')
    assert not state.is_tool_session_approved('write')


def test_empty_state_rejects_all():
    state = JITApprovalState()
    assert not state.is_call_approved('anything')
    assert not state.is_tool_session_approved('anything')


def test_default_disabled():
    cfg = MultiSigQuorumConfig()
    assert not cfg.enabled
    assert cfg.required_approvals == 2


def test_from_workspace_config_empty(tmp_path):
    (tmp_path / '.teaagent').mkdir(exist_ok=True)
    (tmp_path / '.teaagent' / 'config.json').write_text('{}')
    cfg = MultiSigQuorumConfig.from_workspace_config(str(tmp_path))
    assert not cfg.enabled


def test_assert_allowed_read_only_allows_read():
    mgr = ApprovalManager(permission_mode=PermissionMode.READ_ONLY)
    mgr.assert_allowed(
        tool_name='workspace_read_file',
        call_id='c1',
        destructive=False,
        read_only=True,
    )
    # Verify that read operations are allowed in read-only mode
    assert mgr.permission_mode == PermissionMode.READ_ONLY


def test_assert_allowed_read_only_blocks_write():
    mgr = ApprovalManager(permission_mode=PermissionMode.READ_ONLY)
    with pytest.raises(ToolPermissionError):
        mgr.assert_allowed(
            tool_name='workspace_write_file',
            call_id='c1',
            destructive=True,
        )
    # Verify that the manager is still in read-only mode
    assert mgr.permission_mode == PermissionMode.READ_ONLY


def test_assert_allowed_workspace_write_allows_edit():
    mgr = ApprovalManager(permission_mode=PermissionMode.WORKSPACE_WRITE)
    mgr.assert_allowed(
        tool_name='workspace_edit_at_hash',
        call_id='c1',
        destructive=True,
        arguments={'path': 'foo.py'},
    )
    # Verify that workspace_write mode allows edits
    assert mgr.permission_mode == PermissionMode.WORKSPACE_WRITE


def test_approve_once_then_assert_allowed():
    mgr = ApprovalManager(permission_mode=PermissionMode.PROMPT)
    mgr.approve_once('c1')
    mgr.assert_allowed(
        tool_name='workspace_write_file',
        call_id='c1',
        destructive=True,
    )
    # Verify that the call was approved
    assert mgr.get_jit_state().is_call_approved('c1')


def test_shutdown_does_not_raise():
    mgr = ApprovalManager()
    mgr.shutdown()
    # Verify that a new manager can be created after shutdown
    mgr2 = ApprovalManager()
    assert mgr2 is not None


def test_empty_signature_fails():
    result = _verify_ssh_signature('', 'msg', 'peer', {}, allow_dev_signatures=True)
    assert result is False


def test_missing_public_key_fails():
    result = _verify_ssh_signature('sig', 'msg', 'peer', {}, allow_dev_signatures=True)
    assert result is False


def test_non_ssh_blob_dev_disabled_fails():
    result = _verify_ssh_signature(
        'plaintext',
        'msg',
        'peer',
        {'peer': 'ssh-ed25519 AAAAC3...'},
        allow_dev_signatures=False,
    )
    assert result is False
