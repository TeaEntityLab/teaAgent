from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from teaagent.errors import ToolPermissionError
from teaagent.policy import (
    ApprovalPolicy,
    PermissionMode,
    parse_permission_mode,
)


class PermissionModeTests(unittest.TestCase):
    def test_all_modes_are_accessible(self) -> None:
        self.assertEqual(PermissionMode.READ_ONLY, 'read-only')
        self.assertEqual(PermissionMode.WORKSPACE_WRITE, 'workspace-write')
        self.assertEqual(PermissionMode.PROMPT, 'prompt')
        self.assertEqual(PermissionMode.ALLOW, 'allow')
        self.assertEqual(PermissionMode.DANGER_FULL_ACCESS, 'danger-full-access')


class ParsePermissionModeTests(unittest.TestCase):
    def test_parses_valid_modes(self) -> None:
        self.assertIs(parse_permission_mode('read-only'), PermissionMode.READ_ONLY)
        self.assertIs(
            parse_permission_mode('workspace-write'), PermissionMode.WORKSPACE_WRITE
        )
        self.assertIs(parse_permission_mode('prompt'), PermissionMode.PROMPT)
        self.assertIs(parse_permission_mode('allow'), PermissionMode.ALLOW)
        self.assertIs(
            parse_permission_mode('danger-full-access'),
            PermissionMode.DANGER_FULL_ACCESS,
        )

    def test_raises_on_unknown_mode(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            parse_permission_mode('invalid')
        self.assertIn('unknown permission mode', str(ctx.exception))
        self.assertIn('Available:', str(ctx.exception))


class ApprovalPolicyTests(unittest.TestCase):
    def test_non_destructive_tool_always_allowed(self) -> None:
        for mode in PermissionMode:
            policy = ApprovalPolicy(permission_mode=mode)
            policy.assert_allowed(
                tool_name='workspace_read_file', call_id='c1', destructive=False
            )

    def test_read_only_blocks_destructive(self) -> None:
        policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
        with self.assertRaises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file', call_id='c1', destructive=True
            )
        self.assertIn('read-only', str(ctx.exception))

    def test_workspace_write_allows_file_write_tools(self) -> None:
        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        for tool_name in {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
        }:
            policy.assert_allowed(tool_name=tool_name, call_id='c1', destructive=True)

    def test_workspace_write_blocks_shell_destructive(self) -> None:
        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        with self.assertRaises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_run_shell_mutate', call_id='c1', destructive=True
            )
        self.assertIn('prompt/allow/danger-full-access', str(ctx.exception))

    def test_allow_mode_passes_destructive(self) -> None:
        policy = ApprovalPolicy(permission_mode=PermissionMode.ALLOW)
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='c1', destructive=True
        )

    def test_danger_full_access_mode_passes_destructive(self) -> None:
        policy = ApprovalPolicy(permission_mode=PermissionMode.DANGER_FULL_ACCESS)
        policy.assert_allowed(
            tool_name='workspace_run_shell_mutate', call_id='c1', destructive=True
        )

    def test_prompt_mode_with_allow_all_destructive_passes(self) -> None:
        policy = ApprovalPolicy(allow_all_destructive=True)
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='any', destructive=True
        )

    def test_prompt_mode_with_approved_call_id_passes(self) -> None:
        policy = ApprovalPolicy(approved_call_ids=frozenset({'call-42'}))
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='call-42', destructive=True
        )

    def test_prompt_mode_without_approval_blocks(self) -> None:
        policy = ApprovalPolicy()
        with self.assertRaises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file', call_id='unapproved', destructive=True
            )
        self.assertIn('explicit approval', str(ctx.exception))

    def test_policy_is_frozen(self) -> None:
        policy = ApprovalPolicy()
        with self.assertRaises(FrozenInstanceError):
            policy.allow_all_destructive = True  # type: ignore[misc]


if __name__ == '__main__':
    unittest.main()
