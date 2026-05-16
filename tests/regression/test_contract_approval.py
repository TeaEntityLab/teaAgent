"""Regression contract: destructive-tool approval must never be bypassed.

This is an indestructible contract — if this test fails, the approval
policy has a regression that could allow unapproved destructive operations.
"""

from __future__ import annotations

from teaagent.policy import ApprovalPolicy, PermissionMode


def test_read_only_mode_blocks_all_destructive() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    for tool in (
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
        'workspace_run_shell_mutate',
    ):
        raised = False
        try:
            policy.assert_allowed(tool_name=tool, call_id='x', destructive=True)
        except Exception:
            raised = True
        assert raised, f'{tool} must be blocked in read-only mode'


def test_workspace_write_allows_file_writes_blocks_shell() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
    for tool in (
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    ):
        policy.assert_allowed(tool_name=tool, call_id='x', destructive=True)
    for tool in ('workspace_run_shell_mutate', 'bash'):
        raised = False
        try:
            policy.assert_allowed(tool_name=tool, call_id='x', destructive=True)
        except Exception:
            raised = True
        assert raised, f'{tool} must be blocked in workspace-write mode'


def test_unapproved_destructive_call_raises_in_prompt_mode() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    raised = False
    try:
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='unknown', destructive=True
        )
    except Exception:
        raised = True
    assert raised


def test_approved_call_id_passes_in_prompt_mode() -> None:
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approved_call_ids=frozenset({'approved-1'}),
    )
    policy.assert_allowed(
        tool_name='workspace_write_file', call_id='approved-1', destructive=True
    )


def test_allow_mode_accepts_all_destructive() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.ALLOW)
    for tool in ('workspace_write_file', 'workspace_run_shell_mutate'):
        policy.assert_allowed(tool_name=tool, call_id='x', destructive=True)


def test_danger_full_access_accepts_all_destructive() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.DANGER_FULL_ACCESS)
    for tool in ('workspace_write_file', 'workspace_run_shell_mutate'):
        policy.assert_allowed(tool_name=tool, call_id='x', destructive=True)


def test_non_destructive_tool_never_raises() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
    policy.assert_allowed(
        tool_name='workspace_read_file', call_id='x', destructive=False
    )
    policy.assert_allowed(
        tool_name='workspace_search_text', call_id='x', destructive=False
    )


def test_allow_all_destructive_flag_bypasses_approval() -> None:
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        allow_all_destructive=True,
    )
    policy.assert_allowed(
        tool_name='workspace_write_file', call_id='any', destructive=True
    )
