from __future__ import annotations

import tempfile
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

    def test_scoped_approval_blocks_same_call_id_different_tool(self) -> None:
        """Regression test: same call_id with different tool/args must be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'test-run-123'

            # Add scoped approval for workspace_write_file with specific arguments
            store.add_scoped_approval(
                run_id=run_id,
                call_id='write-1',
                tool_name='workspace_write_file',
                arguments={'path': 'safe.txt', 'content': 'hello'},
            )

            # Create policy with scoped approval checking
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id=run_id,
            )

            # This should pass - exact match
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='write-1',
                destructive=True,
                arguments={'path': 'safe.txt', 'content': 'hello'},
            )

            # This should fail - same call_id but different tool
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_run_shell_mutate',
                    call_id='write-1',
                    destructive=True,
                    arguments={'command': 'rm -rf build'},
                )
            self.assertIn('explicit approval', str(ctx.exception))

            # This should fail - same call_id and tool but different arguments
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='write-1',
                    destructive=True,
                    arguments={'path': 'dangerous.txt', 'content': 'malicious'},
                )
            self.assertIn('explicit approval', str(ctx.exception))

    def test_scoped_approval_blocks_sensitive_command_mismatch(self) -> None:
        """Verify that shell mutate with a different command is strictly blocked and does not consume the record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'run-cmd-123'

            store.add_scoped_approval(
                run_id=run_id,
                call_id='shell-1',
                tool_name='workspace_run_shell_mutate',
                arguments={'command': 'pytest'},
            )

            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id=run_id,
            )

            # Check with a different command - must fail
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_run_shell_mutate',
                    call_id='shell-1',
                    destructive=True,
                    arguments={'command': 'rm -rf /important'},
                )
            self.assertIn('explicit approval', str(ctx.exception))

            # The record must NOT be consumed
            records = store.list_scoped_approvals_for_run(run_id)
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0].consumed_at)

    def test_scoped_approval_blocks_sensitive_content_mismatch(self) -> None:
        """Verify that write file with different content is strictly blocked and does not consume the record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'run-content-123'

            store.add_scoped_approval(
                run_id=run_id,
                call_id='write-1',
                tool_name='workspace_write_file',
                arguments={'path': 'out.txt', 'content': 'safe content'},
            )

            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id=run_id,
            )

            # Check with different content - must fail
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='write-1',
                    destructive=True,
                    arguments={'path': 'out.txt', 'content': 'malicious payload'},
                )
            self.assertIn('explicit approval', str(ctx.exception))

            # The record must NOT be consumed
            records = store.list_scoped_approvals_for_run(run_id)
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0].consumed_at)

    def test_scoped_approval_blocks_sensitive_patch_mismatch(self) -> None:
        """Verify that edit with different old/new keys is strictly blocked and does not consume the record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'run-patch-123'

            store.add_scoped_approval(
                run_id=run_id,
                call_id='edit-1',
                tool_name='workspace_apply_patch',
                arguments={'path': 'file.py', 'old': 'print("A")', 'new': 'print("B")'},
            )

            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id=run_id,
            )

            # Check with different new key - must fail
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_apply_patch',
                    call_id='edit-1',
                    destructive=True,
                    arguments={
                        'path': 'file.py',
                        'old': 'print("A")',
                        'new': 'import os; os.system("rm -rf /")',
                    },
                )
            self.assertIn('explicit approval', str(ctx.exception))

            # The record must NOT be consumed
            records = store.list_scoped_approvals_for_run(run_id)
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0].consumed_at)

    def test_hmac_sha256_fingerprint_matching(self) -> None:
        """Verify that v2 HMAC signatures match raw arguments and v1 legacy digests fall back safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'run-hmac-123'
            tool_name = 'workspace_run_shell_mutate'
            arguments = {'command': 'pytest'}

            # 1. Create a scoped approval without explicit digest (will compute v2 digest using workspace secret)
            record_v2 = store.add_scoped_approval(
                run_id=run_id,
                call_id='shell-v2',
                tool_name=tool_name,
                arguments=arguments,
            )

            # Ensure a secure 64-character hex signature was generated (256-bit HMAC)
            self.assertEqual(len(record_v2.argument_digest), 64)

            # Assert policy accepts exact match via v2
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                approval_store=store,
                approval_origin_run_id=run_id,
            )
            policy.assert_allowed(
                tool_name=tool_name,
                call_id='shell-v2',
                destructive=True,
                arguments=arguments,
            )

            # Record must be consumed
            self.assertTrue(store.list_scoped_approvals_for_run(run_id) == [])

            # 2. Add a legacy v1 record explicitly passing a v1 16-hex digest
            from teaagent.ergonomics.approval_store import _compute_argument_digest

            v1_digest = _compute_argument_digest(arguments)
            self.assertEqual(len(v1_digest), 16)

            store.add_scoped_approval(
                run_id=run_id,
                call_id='shell-v1',
                tool_name=tool_name,
                arguments=arguments,
                argument_digest=v1_digest,
            )

            # Assert policy accepts fallback match via v1
            policy.assert_allowed(
                tool_name=tool_name,
                call_id='shell-v1',
                destructive=True,
                arguments=arguments,
            )

    def test_resume_deduplication(self) -> None:
        """Verify that check_scoped_approval_digest prevents duplicate scoped approvals on multiple resumes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            run_id = 'run-dedupe-123'
            tool_name = 'workspace_write_file'
            arguments = {'path': 'test.txt', 'content': 'hello'}
            digest = 'dummy-digest-12345'

            # First add should succeed
            has_existing = store.check_scoped_approval_digest(
                run_id=run_id,
                call_id='write-1',
                tool_name=tool_name,
                argument_digest=digest,
            )
            self.assertIsNone(has_existing)

            store.add_scoped_approval(
                run_id=run_id,
                call_id='write-1',
                tool_name=tool_name,
                arguments=arguments,
                argument_digest=digest,
            )

            # Second check should find the existing record
            has_existing = store.check_scoped_approval_digest(
                run_id=run_id,
                call_id='write-1',
                tool_name=tool_name,
                argument_digest=digest,
            )
            self.assertIsNotNone(has_existing)
            self.assertEqual(has_existing.argument_digest, digest)


if __name__ == '__main__':
    unittest.main()
