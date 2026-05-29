"""Permission mode matrix for destructive tool governance."""

from __future__ import annotations

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy, PermissionMode


@pytest.mark.parametrize(
    ('mode', 'tool_name', 'destructive', 'should_allow'),
    [
        (PermissionMode.READ_ONLY, 'workspace_read_file', False, True),
        (PermissionMode.READ_ONLY, 'workspace_write_file', True, False),
        (PermissionMode.WORKSPACE_WRITE, 'workspace_write_file', True, True),
        (PermissionMode.WORKSPACE_WRITE, 'workspace_run_shell_mutate', True, False),
        (PermissionMode.WORKSPACE_WRITE, 'workspace_read_file', False, True),
        (PermissionMode.ALLOW, 'workspace_run_shell_mutate', True, True),
        (PermissionMode.DANGER_FULL_ACCESS, 'workspace_run_shell_mutate', True, True),
    ],
)
def test_permission_matrix(
    mode: PermissionMode,
    tool_name: str,
    destructive: bool,
    should_allow: bool,
) -> None:
    policy = ApprovalPolicy(permission_mode=mode)
    if should_allow:
        policy.assert_allowed(
            tool_name=tool_name,
            call_id='call-matrix',
            destructive=destructive,
        )
    else:
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name=tool_name,
                call_id='call-matrix',
                destructive=destructive,
            )


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
