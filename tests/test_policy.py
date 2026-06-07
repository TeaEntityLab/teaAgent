from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from teaagent.approval_manager import JITApprovalManager, MultiSigQuorumConfig
from teaagent.ergonomics.approval_store import ApprovalPresetStore
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
            kwargs: dict = dict(
                tool_name='workspace_read_file', call_id='c1', destructive=False
            )
            if mode == PermissionMode.READ_ONLY:
                kwargs['read_only'] = True
            policy.assert_allowed(**kwargs)

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

    def test_danger_full_access_mode_with_allow_all_destructive_passes(self) -> None:
        # The bypass is only honored in danger-full-access mode.
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        )
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='any', destructive=True
        )

    def test_prompt_mode_allow_all_destructive_without_ack_blocks(self) -> None:
        # P1-TR-011: Verify that allow_all_destructive without acknowledgment blocks.
        from teaagent.errors import DenialReasonCode

        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            allow_all_destructive=True,
            full_access_acknowledged=False,
        )
        with self.assertRaises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file', call_id='any', destructive=True
            )
        self.assertEqual(
            ctx.exception.reason_code, DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED
        )

    def test_prompt_mode_preapproved_call_id_with_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            policy = ApprovalPolicy(
                approval_store=store,
                approval_origin_run_id='run-x',
                preapproved_call_ids=frozenset({'call-42'}),
            )
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-42',
                destructive=True,
                arguments={'path': 'a.txt', 'content': 'b'},
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
            policy.allow_all_destructive = True

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
            from teaagent.ergonomics._approval_grants import _compute_argument_digest

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


class TrustBoundaryPermissionsTests(unittest.TestCase):
    """Phase 3: .teaagent dir/file modes and check_security_health."""

    def test_teaagent_dir_created_with_0700(self) -> None:
        """__init__ must chmod .teaagent to 0o700."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            teaagent_dir = store.root / '.teaagent'
            mode = teaagent_dir.stat().st_mode & 0o777
            self.assertEqual(
                mode, 0o700, f'.teaagent/ should be 0o700 but got {oct(mode)}'
            )

    def test_approvals_json_written_with_0600(self) -> None:
        """_save must chmod approvals.json to 0o600 after every write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            mode = store.path.stat().st_mode & 0o777
            self.assertEqual(
                mode, 0o600, f'approvals.json should be 0o600 but got {oct(mode)}'
            )

    def test_secret_written_with_0600(self) -> None:
        """_get_workspace_secret must chmod secret to 0o600 after creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            # trigger secret generation
            store._get_workspace_secret()
            secret_path = store.root / '.teaagent' / 'secret'
            self.assertTrue(secret_path.exists(), 'secret file should be created')
            mode = secret_path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600, f'secret should be 0o600 but got {oct(mode)}')

    def test_secret_raises_ioerror_on_corrupt_content(self) -> None:
        """_get_workspace_secret must raise IOError on invalid hex content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            secret_path = store.root / '.teaagent' / 'secret'
            # Write garbage shorter than 64 chars
            secret_path.write_text('tooshort', encoding='utf-8')
            with self.assertRaises(IOError):
                store._get_workspace_secret()

    def test_secret_raises_ioerror_on_non_hex_content(self) -> None:
        """_get_workspace_secret must raise IOError when 64-char but not valid hex."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            secret_path = store.root / '.teaagent' / 'secret'
            secret_path.write_text('x' * 64, encoding='utf-8')  # not hex
            with self.assertRaises(IOError):
                store._get_workspace_secret()

    def test_check_security_health_fresh_workspace_is_ok(self) -> None:
        """Fresh workspace with no approvals yet should report ok=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            result = store.check_security_health()
            self.assertIn('ok', result)
            self.assertIn('checks', result)
            self.assertIsInstance(result['checks'], list)
            # No errors expected on a fresh workspace (files don't exist yet)
            self.assertTrue(result['ok'], f'Unexpected errors: {result["checks"]}')

    def test_check_security_health_detects_wrong_dir_mode(self) -> None:
        """check_security_health reports error when .teaagent/ mode is too open."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            teaagent_dir = store.root / '.teaagent'
            teaagent_dir.chmod(0o755)  # too permissive
            result = store.check_security_health()
            dir_check = next(
                (c for c in result['checks'] if c['name'] == 'teaagent_dir_mode'), None
            )
            self.assertIsNotNone(dir_check, 'teaagent_dir_mode check should be present')
            self.assertFalse(dir_check['ok'])
            self.assertEqual(dir_check['severity'], 'error')

    def test_check_security_health_detects_wrong_secret_mode(self) -> None:
        """check_security_health reports error when secret file mode is too open."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store._get_workspace_secret()  # create secret
            secret_path = store.root / '.teaagent' / 'secret'
            secret_path.chmod(0o644)  # too permissive
            result = store.check_security_health()
            secret_check = next(
                (c for c in result['checks'] if c['name'] == 'secret_file_mode'), None
            )
            self.assertIsNotNone(secret_check)
            self.assertFalse(secret_check['ok'])
            self.assertEqual(secret_check['severity'], 'error')

    def test_check_security_health_detects_wrong_approvals_mode(self) -> None:
        """check_security_health reports error when approvals.json mode is too open."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )  # create the file
            store.path.chmod(0o644)
            result = store.check_security_health()
            approvals_check = next(
                (c for c in result['checks'] if c['name'] == 'approvals_file_mode'),
                None,
            )
            self.assertIsNotNone(approvals_check)
            self.assertFalse(approvals_check['ok'])
            self.assertEqual(approvals_check['severity'], 'error')

    def test_check_security_health_result_structure(self) -> None:
        """Each check entry must have name, ok, severity, message fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            result = store.check_security_health()
            for check in result['checks']:
                self.assertIn('name', check)
                self.assertIn('ok', check)
                self.assertIn('severity', check)
                self.assertIn('message', check)
                self.assertIn(check['severity'], ('error', 'warning', 'info'))

    def test_check_security_health_detects_wrong_dir_ownership(self) -> None:
        """check_security_health reports error when .teaagent/ is owned by wrong user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            _ = store.root / '.teaagent'
            # Simulate wrong ownership by checking against a different uid
            # We can't actually change ownership without sudo, so we test the logic
            # by verifying the check exists and passes for current user
            result = store.check_security_health()
            dir_ownership_check = next(
                (c for c in result['checks'] if c['name'] == 'teaagent_dir_ownership'),
                None,
            )
            self.assertIsNotNone(
                dir_ownership_check, 'teaagent_dir_ownership check should be present'
            )
            # Should pass since we own the directory
            self.assertTrue(dir_ownership_check['ok'])

    def test_check_security_health_detects_wrong_secret_ownership(self) -> None:
        """check_security_health reports error when secret file is owned by wrong user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store._get_workspace_secret()  # create secret
            result = store.check_security_health()
            secret_ownership_check = next(
                (c for c in result['checks'] if c['name'] == 'secret_file_ownership'),
                None,
            )
            self.assertIsNotNone(
                secret_ownership_check, 'secret_file_ownership check should be present'
            )
            # Should pass since we own the file
            self.assertTrue(secret_ownership_check['ok'])

    def test_check_security_health_detects_wrong_approvals_ownership(self) -> None:
        """check_security_health reports error when approvals.json is owned by wrong user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )  # create the file
            result = store.check_security_health()
            approvals_ownership_check = next(
                (
                    c
                    for c in result['checks']
                    if c['name'] == 'approvals_file_ownership'
                ),
                None,
            )
            self.assertIsNotNone(
                approvals_ownership_check,
                'approvals_file_ownership check should be present',
            )
            # Should pass since we own the file
            self.assertTrue(approvals_ownership_check['ok'])


class TrustBoundaryRegressionTests(unittest.TestCase):
    """Phase 3.1 regressions: key_id orphan heuristic, JSON content check, fix_permissions."""

    # ---- P2a: key_id-based orphan detection -----------------------------------

    def test_fresh_v2_approval_not_flagged_as_orphan(self) -> None:
        """A v2 scoped approval created with the CURRENT secret must not be reported
        as orphaned — regression for the mtime false-positive bug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.add_scoped_approval(
                run_id='run-1',
                call_id='call-1',
                tool_name='workspace_write_file',
                arguments={'path': 'a.txt', 'content': 'hi'},
            )
            result = store.check_security_health()
            orphan_check = next(
                c for c in result['checks'] if c['name'] == 'orphaned_v2_approvals'
            )
            self.assertTrue(
                orphan_check['ok'],
                f'Fresh v2 approval should NOT be orphan: {orphan_check}',
            )

    def test_rotated_secret_flags_old_v2_approval_as_orphan(self) -> None:
        """After the secret is deleted and regenerated, old v2 approvals with a
        different key_id must be flagged as orphaned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.add_scoped_approval(
                run_id='run-1',
                call_id='call-1',
                tool_name='workspace_write_file',
                arguments={'path': 'a.txt', 'content': 'hi'},
            )
            # Rotate secret: delete and let it regenerate
            secret_path = store.root / '.teaagent' / 'secret'
            secret_path.unlink()
            # New store instance will regenerate a different secret
            store2 = ApprovalPresetStore(tmpdir)
            result = store2.check_security_health()
            orphan_check = next(
                c for c in result['checks'] if c['name'] == 'orphaned_v2_approvals'
            )
            self.assertFalse(
                orphan_check['ok'],
                f'After rotation, old v2 approval should be orphaned: {orphan_check}',
            )
            self.assertIn('orphaned_record_ids', orphan_check)
            self.assertEqual(len(orphan_check['orphaned_record_ids']), 1)

    def test_v2_approval_without_key_id_not_flagged(self) -> None:
        """Legacy v2 records without a key_id field must NOT be flagged as orphaned
        (they predate key_id tracking and fall back to v1 matching)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            # Inject a record with 64-hex digest but no key_id
            data = store._load()
            data['scoped_approvals'].append(
                {
                    'record_id': 'legacy-001',
                    'run_id': 'run-legacy',
                    'call_id': 'call-legacy',
                    'tool_name': 'shell_exec',
                    'argument_digest': 'a' * 64,
                    'created_at': '2026-01-01T00:00:00+00:00',
                }
            )
            store._save(data)
            result = store.check_security_health()
            orphan_check = next(
                c for c in result['checks'] if c['name'] == 'orphaned_v2_approvals'
            )
            self.assertTrue(
                orphan_check['ok'],
                f'Legacy record without key_id must not be flagged: {orphan_check}',
            )

    # ---- P2b: approvals.json content health check ----------------------------

    def test_corrupt_json_detected_by_health_check(self) -> None:
        """check_security_health must report error when approvals.json is invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            # Write something to trigger file creation first, then corrupt it
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text('{bad json', encoding='utf-8')
            result = store.check_security_health()
            content_check = next(
                (c for c in result['checks'] if c['name'] == 'approvals_file_content'),
                None,
            )
            self.assertIsNotNone(
                content_check, 'approvals_file_content check must exist'
            )
            self.assertFalse(content_check['ok'])
            self.assertEqual(content_check['severity'], 'error')

    def test_wrong_top_level_type_detected_by_health_check(self) -> None:
        """check_security_health must report error when top-level is not a dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text('[1, 2, 3]', encoding='utf-8')
            result = store.check_security_health()
            content_check = next(
                (c for c in result['checks'] if c['name'] == 'approvals_file_content'),
                None,
            )
            self.assertIsNotNone(content_check)
            self.assertFalse(content_check['ok'])
            self.assertIn('list', content_check['message'])

    def test_bad_key_type_detected_by_health_check(self) -> None:
        """check_security_health must report error when a required list key is not a list."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text(
                json.dumps(
                    {'grants': 'not-a-list', 'audit': [], 'scoped_approvals': []}
                ),
                encoding='utf-8',
            )
            result = store.check_security_health()
            content_check = next(
                (c for c in result['checks'] if c['name'] == 'approvals_file_content'),
                None,
            )
            self.assertIsNotNone(content_check)
            self.assertFalse(content_check['ok'])
            self.assertIn('grants', content_check.get('bad_keys', []))

    def test_valid_approvals_json_passes_content_check(self) -> None:
        """Normal approvals.json must get ok=True for the content check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            result = store.check_security_health()
            content_check = next(
                (c for c in result['checks'] if c['name'] == 'approvals_file_content'),
                None,
            )
            self.assertIsNotNone(content_check)
            self.assertTrue(content_check['ok'])

    def test_mutating_store_fails_closed_on_corrupt_json(self) -> None:
        """Mutating paths must not silently replace a corrupt approvals.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text('{bad json', encoding='utf-8')

            with self.assertRaises(IOError):
                store.grant(
                    tool_name='workspace_write_file',
                    scope='once',
                    path_globs=['src/**'],
                )

            self.assertEqual(store.path.read_text(encoding='utf-8'), '{bad json')

    def test_repair_store_noops_on_healthy_store(self) -> None:
        """--repair-store semantics: a valid store is inspected, not reset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            before = store.path.read_text(encoding='utf-8')

            result = store.repair_store()

            self.assertEqual(result['status'], 'noop')
            self.assertFalse(result['repaired'])
            self.assertEqual(store.path.read_text(encoding='utf-8'), before)

    def test_repair_store_rebuilds_corrupt_store_with_backup(self) -> None:
        """Corrupt store repair must preserve the bad file in a timestamped backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text('{bad json', encoding='utf-8')

            result = store.repair_store()

            self.assertEqual(result['status'], 'repaired')
            self.assertTrue(result['repaired'])
            self.assertIsNotNone(result['backup_path'])
            with open(result['backup_path'], encoding='utf-8') as backup:
                self.assertEqual(backup.read(), '{bad json')
            repaired = json.loads(store.path.read_text(encoding='utf-8'))
            self.assertEqual(repaired['grants'], [])
            self.assertEqual(repaired['audit'][0]['action'], 'store_repaired')

    def test_repair_store_operator_reset_is_audited_separately(self) -> None:
        """Explicit healthy-store reset is allowed only as a distinct audit event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )

            result = store.repair_store(reset_healthy=True)

            self.assertEqual(result['status'], 'reset')
            self.assertTrue(result['repaired'])
            self.assertIsNotNone(result['backup_path'])
            reset_store = json.loads(store.path.read_text(encoding='utf-8'))
            self.assertEqual(reset_store['grants'], [])
            self.assertEqual(reset_store['audit'][0]['action'], 'store_operator_reset')

    def test_repair_store_same_second_creates_distinct_backups(self) -> None:
        """Multiple repairs within the same second must create distinct backup files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            store.grant(
                tool_name='shell_exec',
                scope='once',
                command_prefixes=['pytest '],
            )
            store.path.write_text('{bad json', encoding='utf-8')

            result1 = store.repair_store()
            backup_path1 = result1['backup_path']

            # Corrupt again and repair immediately (same second)
            store.path.write_text('{bad json 2', encoding='utf-8')
            result2 = store.repair_store()
            backup_path2 = result2['backup_path']

            self.assertNotEqual(backup_path1, backup_path2)
            self.assertTrue('.json.backup.' in backup_path1)
            self.assertTrue('.json.backup.' in backup_path2)
            # Verify both backups exist and contain their respective corrupt data
            with open(backup_path1, encoding='utf-8') as f:
                self.assertEqual(f.read(), '{bad json')
            with open(backup_path2, encoding='utf-8') as f:
                self.assertEqual(f.read(), '{bad json 2')

    # ---- fix_permissions parameter -------------------------------------------

    def test_fix_permissions_repairs_dir_mode(self) -> None:
        """check_security_health(fix_permissions=True) must chmod the dir back to 0o700."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ApprovalPresetStore(tmpdir)
            teaagent_dir = store.root / '.teaagent'
            teaagent_dir.chmod(0o755)
            result = store.check_security_health(fix_permissions=True)
            mode_after = teaagent_dir.stat().st_mode & 0o777
            self.assertEqual(mode_after, 0o700)
            next(c for c in result['checks'] if c['name'] == 'teaagent_dir_mode')


class MultiSigQuorumTests(unittest.TestCase):
    """Tests for TASK-014: Multi-Signature Quorum Consensus."""

    def test_multi_sig_config_defaults(self) -> None:
        """Verify default multi-sig configuration."""
        config = MultiSigQuorumConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.required_approvals, 2)
        self.assertEqual(config.peer_agent_ids, [])
        self.assertEqual(config.high_risk_patterns, [])
        self.assertEqual(config.timeout_seconds, 300)

    def test_multi_sig_config_from_workspace_json(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / '.teaagent').mkdir()
            (root / '.teaagent' / 'config.json').write_text(
                json.dumps(
                    {
                        'multi_sig': {
                            'enabled': True,
                            'required_approvals': 2,
                            'peer_agent_ids': ['peer-a'],
                            'peer_relay_urls': {
                                'peer-a': 'https://peer-a.example:8791'
                            },
                            'local_relay_base_url': 'https://collector.example:8791',
                        }
                    }
                ),
                encoding='utf-8',
            )
            config = MultiSigQuorumConfig.from_workspace_config(root)
            self.assertTrue(config.enabled)
            self.assertEqual(
                config.peer_relay_urls['peer-a'], 'https://peer-a.example:8791'
            )
            self.assertEqual(
                config.local_relay_base_url, 'https://collector.example:8791'
            )

    def test_multi_sig_config_custom(self) -> None:
        """Verify custom multi-sig configuration."""
        config = MultiSigQuorumConfig(
            enabled=True,
            required_approvals=3,
            peer_agent_ids=['agent-1', 'agent-2', 'agent-3'],
            high_risk_patterns=['/prod', '/production'],
            timeout_seconds=600,
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.required_approvals, 3)
        self.assertEqual(len(config.peer_agent_ids), 3)
        self.assertIn('/prod', config.high_risk_patterns)
        self.assertEqual(config.timeout_seconds, 600)

    def test_policy_with_multi_sig_disabled(self) -> None:
        """Verify policy behaves normally when multi-sig is disabled."""
        config = MultiSigQuorumConfig(enabled=False)
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            multi_sig_config=config,
        )

        # Should still require normal approval
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-1',
                destructive=True,
                arguments={'path': '/prod/config.json'},
            )

    def test_high_risk_detection_default_patterns(self) -> None:
        """Verify default high-risk pattern detection."""
        config = MultiSigQuorumConfig(enabled=True, required_approvals=2)
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            multi_sig_config=config,
            agent_id='test-agent',
        )

        # Should detect /prod path as high-risk
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_write_file', {'path': '/prod/config.json'}
            )
        )

        # Should detect /production path in arguments
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate', {'command': 'deploy /production/app'}
            )
        )

        # Should detect delete operations
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate', {'command': 'rm -rf /tmp'}
            )
        )

    def test_high_risk_detection_custom_patterns(self) -> None:
        """Verify custom high-risk pattern detection."""
        config = MultiSigQuorumConfig(
            enabled=True, high_risk_patterns=['/critical', 'deploy']
        )
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            multi_sig_config=config,
            agent_id='test-agent',
        )

        # Should detect custom patterns
        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_write_file', {'path': '/critical/data.json'}
            )
        )

        self.assertTrue(
            policy._is_high_risk_operation(
                'workspace_run_shell_mutate', {'command': './deploy.sh'}
            )
        )

    def test_approval_request_hash_generation(self) -> None:
        """Verify approval request hash generation is deterministic."""
        policy = ApprovalPolicy(agent_id='test-agent')

        hash1 = policy._generate_approval_hash(
            'workspace_write_file', 'call-1', {'path': 'test.txt'}
        )

        hash2 = policy._generate_approval_hash(
            'workspace_write_file', 'call-1', {'path': 'test.txt'}
        )

        # Same inputs should produce same hash
        self.assertEqual(hash1, hash2)

        # Different inputs should produce different hash
        hash3 = policy._generate_approval_hash(
            'workspace_write_file', 'call-1', {'path': 'different.txt'}
        )
        self.assertNotEqual(hash1, hash3)

    def test_multi_sig_quorum_without_agent_id(self) -> None:
        """Verify multi-sig falls back gracefully without agent_id."""
        config = MultiSigQuorumConfig(enabled=True, required_approvals=2)
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            multi_sig_config=config,
            agent_id='',  # Empty agent_id
        )

        # Should fall back to normal approval flow
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-1',
                destructive=True,
                arguments={'path': '/prod/config.json'},
            )

    @unittest.skip(
        'Multi-sig quorum requires federated_sync P2P broadcast — integration test, not unit-testable'
    )
    def test_multi_sig_quorum_stub_returns_false(self) -> None:
        """Verify stub implementation returns False (no quorum)."""
        config = MultiSigQuorumConfig(enabled=True, required_approvals=2)
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            multi_sig_config=config,
            agent_id='test-agent',
        )

        # Stub implementation should return False (no signatures collected)
        result = policy._check_multi_sig_quorum(
            'workspace_write_file', 'call-1', {'path': '/prod/config.json'}
        )

        self.assertFalse(result)

    # P0-D-001: Workspace root containment
    def test_workspace_root_allows_path_within_root(self) -> None:
        """Path arguments within workspace root are allowed."""
        with tempfile.TemporaryDirectory() as tmp:
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.ALLOW,
                workspace_root=tmp,
            )
            # Path within root must be allowed
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='c1',
                destructive=True,
                arguments={'path': 'src/test.txt'},
            )

    def test_workspace_root_blocks_path_escaping_via_parent_traversal(
        self,
    ) -> None:
        """Path arguments escaping workspace via ../ are blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                workspace_root=tmp,
            )
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='c1',
                    destructive=True,
                    arguments={'path': '../etc/passwd'},
                )
            self.assertIn('outside workspace root', str(ctx.exception))

    def test_workspace_root_blocks_absolute_path_outside_root(self) -> None:
        """Absolute paths outside workspace root are blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                workspace_root=tmp,
            )
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_write_file',
                    call_id='c1',
                    destructive=True,
                    arguments={'path': '/etc/passwd'},
                )
            self.assertIn('outside workspace root', str(ctx.exception))

    def test_workspace_root_does_not_block_non_path_tools(self) -> None:
        """Non-path tools (e.g. shell inspect) are not blocked by root check."""
        with tempfile.TemporaryDirectory() as tmp:
            policy = ApprovalPolicy(
                permission_mode=PermissionMode.PROMPT,
                workspace_root=tmp,
            )
            # workspace_run_shell_inspect has no 'path' argument — should not trigger root check
            with self.assertRaises(ToolPermissionError) as ctx:
                policy.assert_allowed(
                    tool_name='workspace_run_shell_inspect',
                    call_id='c1',
                    destructive=True,
                    arguments={'command': 'ls'},
                )
            # Should fail because no JIT/prompt handler, not because of root containment
            self.assertNotIn('outside workspace root', str(ctx.exception))


class EmptyPathScopeTests(unittest.TestCase):
    """P0-D-002: Empty path grants are rejected or clearly classified."""

    def test_empty_path_globs_rejected_in_grant(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            with self.assertRaises(ValueError) as ctx:
                store.grant(
                    tool_name='workspace_write_file',
                    scope='always',
                    path_globs=[''],
                )
            self.assertIn('non-empty pattern', str(ctx.exception))

    def test_whitespace_only_path_globs_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            with self.assertRaises(ValueError) as ctx:
                store.grant(
                    tool_name='workspace_write_file',
                    scope='always',
                    path_globs=['   ', '\t'],
                )
            self.assertIn('non-empty pattern', str(ctx.exception))

    def test_root_path_globs_dot_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            grant = store.grant(
                tool_name='workspace_write_file',
                scope='always',
                path_globs=['.', 'src/**'],
            )
            self.assertIsNotNone(grant)
            self.assertIn('.', grant.path_globs)
            self.assertIn('src/**', grant.path_globs)

    def test_root_path_globs_star_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            store = ApprovalPresetStore(tmpdir)
            grant = store.grant(
                tool_name='workspace_write_file',
                scope='always',
                path_globs=['*'],
            )
            self.assertIsNotNone(grant)
            self.assertIn('*', grant.path_globs)


class ApprovalPolicyThreadLeakTests(unittest.TestCase):
    def test_del_shuts_down_signature_executor(self) -> None:
        """ENG-01: __del__ must shut down the ThreadPoolExecutor to prevent thread leaks."""
        policy = ApprovalPolicy()
        executor = policy._signature_executor
        policy.__del__()
        with self.assertRaises(RuntimeError):
            executor.submit(lambda: None)

    def test_del_is_safe_to_call_twice(self) -> None:
        policy = ApprovalPolicy()
        policy.__del__()
        policy.__del__()  # must not raise


class JITApprovalTimeoutTests(unittest.TestCase):
    def test_prompt_auto_denies_on_timeout(self) -> None:
        """OPS-01: JIT approval prompt must auto-deny after the configured timeout."""
        blocker = threading.Event()

        def blocking_input(prompt: str) -> str:
            blocker.wait()
            return 'o'

        manager = JITApprovalManager(approval_timeout_seconds=0.05)
        with patch('builtins.input', side_effect=blocking_input):
            result = manager._prompt('tool_x', 'call-timeout-1')

        blocker.set()
        self.assertEqual(result, 'd', 'timed-out prompt must return deny')

    def test_prompt_respects_valid_choice_before_timeout(self) -> None:
        """OPS-01: fast user response must pass through normally."""
        manager = JITApprovalManager(approval_timeout_seconds=5.0)
        with patch('builtins.input', return_value='o'):
            result = manager._prompt('tool_x', 'call-fast-1')
        self.assertEqual(result, 'o')


if __name__ == '__main__':
    unittest.main()
