"""Permission mode matrix for destructive tool governance."""

from __future__ import annotations

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy, PermissionMode


@pytest.mark.parametrize(
    ('mode', 'tool_name', 'destructive', 'read_only', 'should_allow'),
    [
        (PermissionMode.READ_ONLY, 'workspace_read_file', False, True, True),
        (PermissionMode.READ_ONLY, 'workspace_write_file', True, False, False),
        (PermissionMode.READ_ONLY, 'workspace_write_file', False, False, False),
        (PermissionMode.READ_ONLY, 'workspace_run_shell_mutate', False, False, False),
        (PermissionMode.READ_ONLY, 'custom_plugin_save', False, False, False),
        (PermissionMode.READ_ONLY, 'custom_plugin_save', False, True, False),
        (
            PermissionMode.WORKSPACE_WRITE,
            'workspace_write_file',
            True,
            False,
            True,
        ),
        (
            PermissionMode.WORKSPACE_WRITE,
            'workspace_run_shell_mutate',
            True,
            False,
            False,
        ),
        (PermissionMode.WORKSPACE_WRITE, 'workspace_read_file', False, True, True),
        (PermissionMode.ALLOW, 'workspace_run_shell_mutate', True, False, True),
        (
            PermissionMode.DANGER_FULL_ACCESS,
            'workspace_run_shell_mutate',
            True,
            False,
            True,
        ),
    ],
)
def test_permission_matrix(
    mode: PermissionMode,
    tool_name: str,
    destructive: bool,
    read_only: bool,
    should_allow: bool,
) -> None:
    policy = ApprovalPolicy(permission_mode=mode)
    description = (
        'read workspace file'
        if tool_name == 'workspace_read_file'
        else 'plugin helper'
    )
    kwargs = {
        'tool_name': tool_name,
        'call_id': 'call-matrix',
        'destructive': destructive,
        'read_only': read_only,
        'description': description,
    }
    if tool_name == 'custom_plugin_save':
        kwargs['description'] = 'save data'
    if should_allow:
        policy.assert_allowed(**kwargs)
    else:
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(**kwargs)


def test_prompt_mode_requires_approval_for_destructive() -> None:
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    with pytest.raises(ToolPermissionError, match='requires explicit approval'):
        policy.assert_allowed(
            tool_name='workspace_run_shell_mutate',
            call_id='call-prompt',
            destructive=True,
        )


def test_prompt_mode_allows_approved_call_id() -> None:
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approved_call_ids=frozenset({'call-approved'}),
    )
    policy.assert_allowed(
        tool_name='workspace_run_shell_mutate',
        call_id='call-approved',
        destructive=True,
    )
