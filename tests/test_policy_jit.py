"""Tests for JIT (Just-In-Time) privilege escalation in policy module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from teaagent.policy import ApprovalPolicy
from teaagent.types import JITApprovalState, PermissionMode, ToolPermissionError


def test_approve_once() -> None:
    """Test approving a single call ID."""
    state = JITApprovalState()
    state.approve_once('call-123')
    assert state.is_call_approved('call-123')
    assert not state.is_call_approved('call-456')


def test_approve_session() -> None:
    """Test approving a tool for the session."""
    state = JITApprovalState()
    state.approve_session('workspace_write_file')
    assert state.is_tool_session_approved('workspace_write_file')
    assert not state.is_tool_session_approved('workspace_apply_patch')


def test_multiple_approvals() -> None:
    """Test multiple approvals in the same state."""
    state = JITApprovalState()
    state.approve_once('call-1')
    state.approve_once('call-2')
    state.approve_session('tool-a')
    state.approve_session('tool-b')

    assert state.is_call_approved('call-1')
    assert state.is_call_approved('call-2')
    assert state.is_tool_session_approved('tool-a')
    assert state.is_tool_session_approved('tool-b')


def test_jit_state_allows_session_approved_tool() -> None:
    """Test that JIT state allows session-approved tools."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()
    jit_state.approve_session('workspace_write_file')

    # Should not raise error
    policy.assert_allowed(
        tool_name='workspace_write_file',
        call_id='call-123',
        destructive=True,
        jit_state=jit_state,
    )


def test_jit_state_allows_once_approved_call() -> None:
    """Test that JIT state allows once-approved call IDs."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()
    jit_state.approve_once('call-123')

    # Should not raise error
    policy.assert_allowed(
        tool_name='workspace_write_file',
        call_id='call-123',
        destructive=True,
        jit_state=jit_state,
    )


def test_jit_state_without_tty_raises_error() -> None:
    """Test that JIT without TTY raises permission error."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with patch('sys.stdin.isatty', return_value=False):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                jit_state=jit_state,
            )
        assert 'requires explicit approval' in str(cm.value)


def test_jit_state_without_jit_state_raises_error() -> None:
    """Test that JIT without jit_state parameter raises permission error.

    Note: In the new architecture, ApprovalManager always has its own JIT state.
    The external jit_state parameter is synced with the manager's state.
    This test is updated to reflect the new behavior where JIT prompting
    still occurs but uses the manager's internal state.
    """
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', return_value='d'),  # Deny the request
    ):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                jit_state=None,  # No external JIT state, but manager has one
            )
        assert 'denied by user' in str(cm.value)


def test_jit_disabled_skips_prompt() -> None:
    """Test that disabled JIT skips interactive prompt."""
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        enable_jit_prompt=False,
    )
    jit_state = JITApprovalState()

    with patch('sys.stdin.isatty', return_value=True):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                jit_state=jit_state,
            )
        assert 'requires explicit approval' in str(cm.value)


def test_jit_prompt_deny_choice() -> None:
    """Test JIT prompt with deny choice."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', return_value='d'),
    ):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                jit_state=jit_state,
            )
        assert 'was denied by user' in str(cm.value)


def test_jit_prompt_explain_choice() -> None:
    """Test JIT prompt with explain choice."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()
    # Use a path within workspace root (default '.') so path containment
    # doesn't pre-empt the JIT prompt
    arguments = {'path': 'test.txt'}

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', return_value='e'),
    ):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                arguments=arguments,
                jit_state=jit_state,
            )
        assert 'requires approval' in str(cm.value)
        assert 'workspace_write_file' in str(cm.value)
        assert 'call-123' in str(cm.value)


def test_jit_prompt_once_choice() -> None:
    """Test JIT prompt with once choice."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', return_value='o'),
    ):
        # Should not raise error
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-123',
            destructive=True,
            jit_state=jit_state,
        )
        # Call ID should be approved
        assert jit_state.is_call_approved('call-123')


def test_jit_prompt_session_choice() -> None:
    """Test JIT prompt with session choice."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', return_value='s'),
    ):
        # Should not raise error
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-123',
            destructive=True,
            jit_state=jit_state,
        )
        # Tool should be session-approved
        assert jit_state.is_tool_session_approved('workspace_write_file')


def test_jit_prompt_interrupted() -> None:
    """Test JIT prompt with keyboard interrupt."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', side_effect=KeyboardInterrupt),
    ):
        with pytest.raises(ToolPermissionError) as cm:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-123',
                destructive=True,
                jit_state=jit_state,
            )
        assert 'was denied by user' in str(cm.value)


def test_jit_prompt_invalid_then_valid() -> None:
    """Test JIT prompt with invalid input followed by valid input."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    with (
        patch('sys.stdin.isatty', return_value=True),
        patch('builtins.input', side_effect=['x', 'y', 'o']),
    ):
        # Should not raise error after valid input
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-123',
            destructive=True,
            jit_state=jit_state,
        )
        assert jit_state.is_call_approved('call-123')


def test_non_destructive_always_allowed() -> None:
    """Test that non-destructive tools are always allowed."""
    policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
    jit_state = JITApprovalState()

    # Should not raise error for non-destructive
    policy.assert_allowed(
        tool_name='workspace_read_file',
        call_id='call-123',
        destructive=False,
        jit_state=jit_state,
    )
