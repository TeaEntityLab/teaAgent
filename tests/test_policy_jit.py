"""Tests for JIT (Just-In-Time) privilege escalation in policy module."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy, JITApprovalState, PermissionMode


class JITApprovalStateTests(unittest.TestCase):
    def test_approve_once(self) -> None:
        """Test approving a single call ID."""
        state = JITApprovalState()
        state.approve_once('call-123')
        self.assertTrue(state.is_call_approved('call-123'))
        self.assertFalse(state.is_call_approved('call-456'))

    def test_approve_session(self) -> None:
        """Test approving a tool for the session."""
        state = JITApprovalState()
        state.approve_session('workspace_write_file')
        self.assertTrue(state.is_tool_session_approved('workspace_write_file'))
        self.assertFalse(state.is_tool_session_approved('workspace_apply_patch'))

    def test_multiple_approvals(self) -> None:
        """Test multiple approvals in the same state."""
        state = JITApprovalState()
        state.approve_once('call-1')
        state.approve_once('call-2')
        state.approve_session('tool-a')
        state.approve_session('tool-b')

        self.assertTrue(state.is_call_approved('call-1'))
        self.assertTrue(state.is_call_approved('call-2'))
        self.assertTrue(state.is_tool_session_approved('tool-a'))
        self.assertTrue(state.is_tool_session_approved('tool-b'))


class ApprovalPolicyJITTests(unittest.TestCase):
    def test_jit_state_allows_session_approved_tool(self) -> None:
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

    def test_jit_state_allows_once_approved_call(self) -> None:
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

    def test_jit_state_without_tty_raises_error(self) -> None:
        """Test that JIT without TTY raises permission error."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(ToolPermissionError) as cm:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=jit_state,
                )
            self.assertIn('requires explicit approval', str(cm.exception))

    def test_jit_state_without_jit_state_raises_error(self) -> None:
        """Test that JIT without jit_state parameter raises permission error."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)

        with patch('sys.stdin.isatty', return_value=True):
            with self.assertRaises(ToolPermissionError) as cm:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=None,  # No JIT state
                )
            self.assertIn('requires explicit approval', str(cm.exception))

    def test_jit_disabled_skips_prompt(self) -> None:
        """Test that disabled JIT skips interactive prompt."""
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            enable_jit_prompt=False,
        )
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with self.assertRaises(ToolPermissionError) as cm:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=jit_state,
                )
            self.assertIn('requires explicit approval', str(cm.exception))

    def test_jit_prompt_deny_choice(self) -> None:
        """Test JIT prompt with deny choice."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', return_value='d'):
                with self.assertRaises(ToolPermissionError) as cm:
                    policy.assert_allowed(
                        tool_name='workspace_write_file',
                        call_id='call-123',
                        destructive=True,
                        jit_state=jit_state,
                    )
                self.assertIn('was denied by user', str(cm.exception))

    def test_jit_prompt_explain_choice(self) -> None:
        """Test JIT prompt with explain choice."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()
        arguments = {'path': '/tmp/test.txt'}

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', return_value='e'):
                with self.assertRaises(ToolPermissionError) as cm:
                    policy.assert_allowed(
                        tool_name='workspace_write_file',
                        call_id='call-123',
                        destructive=True,
                        arguments=arguments,
                        jit_state=jit_state,
                    )
                self.assertIn('requires approval', str(cm.exception))
                self.assertIn('workspace_write_file', str(cm.exception))
                self.assertIn('call-123', str(cm.exception))

    def test_jit_prompt_once_choice(self) -> None:
        """Test JIT prompt with once choice."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', return_value='o'):
                # Should not raise error
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=jit_state,
                )
                # Call ID should be approved
                self.assertTrue(jit_state.is_call_approved('call-123'))

    def test_jit_prompt_session_choice(self) -> None:
        """Test JIT prompt with session choice."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', return_value='s'):
                # Should not raise error
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=jit_state,
                )
                # Tool should be session-approved
                self.assertTrue(jit_state.is_tool_session_approved('workspace_write_file'))

    def test_jit_prompt_interrupted(self) -> None:
        """Test JIT prompt with keyboard interrupt."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', side_effect=KeyboardInterrupt):
                with self.assertRaises(ToolPermissionError) as cm:
                    policy.assert_allowed(
                        tool_name='workspace_write_file',
                        call_id='call-123',
                        destructive=True,
                        jit_state=jit_state,
                    )
                self.assertIn('was denied by user', str(cm.exception))

    def test_jit_prompt_invalid_then_valid(self) -> None:
        """Test JIT prompt with invalid input followed by valid input."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        jit_state = JITApprovalState()

        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', side_effect=['x', 'y', 'o']):
                # Should not raise error after valid input
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='call-123',
                    destructive=True,
                    jit_state=jit_state,
                )
                self.assertTrue(jit_state.is_call_approved('call-123'))

    def test_non_destructive_always_allowed(self) -> None:
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


if __name__ == '__main__':
    unittest.main()
