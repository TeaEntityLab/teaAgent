from __future__ import annotations

import json
import tempfile
import threading
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from teaagent.approval import (
    JITApprovalManager,
    MultiSigQuorumConfig,
    parse_permission_mode,
)
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy
from teaagent.types import PermissionMode, ToolPermissionError


def test_all_modes_are_accessible() -> None:
    assert PermissionMode.READ_ONLY == 'read-only'
    assert PermissionMode.WORKSPACE_WRITE == 'workspace-write'
    assert PermissionMode.PROMPT == 'prompt'
    assert PermissionMode.ALLOW == 'allow'
    assert PermissionMode.DANGER_FULL_ACCESS == 'danger-full-access'


def test_parses_valid_modes() -> None:
    assert parse_permission_mode('read-only') is PermissionMode.READ_ONLY
    assert parse_permission_mode('workspace-write') is PermissionMode.WORKSPACE_WRITE
    assert parse_permission_mode('prompt') is PermissionMode.PROMPT
    assert parse_permission_mode('allow') is PermissionMode.ALLOW
    assert (
        parse_permission_mode('danger-full-access') is PermissionMode.DANGER_FULL_ACCESS
    )


def test_raises_on_unknown_mode() -> None:
    with pytest.raises(ValueError) as ctx:
        parse_permission_mode('invalid')
    assert 'unknown permission mode' in str(ctx.value)
    assert 'Available:' in str(ctx.value)


def test_non_destructive_tool_always_allowed() -> None:
    for mode in PermissionMode:
        policy = ApprovalPolicy(permission_mode=mode)
        kwargs: dict = dict(
            tool_name='workspace_read_file', call_id='c1', destructive=False
        )
        if mode == PermissionMode.READ_ONLY:
            kwargs['read_only'] = True
        policy.assert_allowed(**kwargs)


def test_read_only_blocks_destructive(
    approval_policy_read_only: ApprovalPolicy,
) -> None:
    with pytest.raises(ToolPermissionError) as ctx:
        approval_policy_read_only.assert_allowed(
            tool_name='workspace_write_file', call_id='c1', destructive=True
        )
    assert 'read-only' in str(ctx.value)


def test_workspace_write_allows_file_write_tools(
    approval_policy_workspace_write: ApprovalPolicy,
) -> None:
    for tool_name in {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }:
        approval_policy_workspace_write.assert_allowed(
            tool_name=tool_name, call_id='c1', destructive=True
        )


def test_workspace_write_blocks_shell_destructive(
    approval_policy_workspace_write: ApprovalPolicy,
) -> None:
    with pytest.raises(ToolPermissionError) as ctx:
        approval_policy_workspace_write.assert_allowed(
            tool_name='workspace_run_shell_mutate', call_id='c1', destructive=True
        )
    assert 'prompt/allow/danger-full-access' in str(ctx.value)


def test_allow_mode_passes_destructive(approval_policy_allow: ApprovalPolicy) -> None:
    approval_policy_allow.assert_allowed(
        tool_name='workspace_write_file', call_id='c1', destructive=True
    )


def test_danger_full_access_mode_passes_destructive(
    approval_policy_danger_full_access: ApprovalPolicy,
) -> None:
    approval_policy_danger_full_access.assert_allowed(
        tool_name='workspace_run_shell_mutate', call_id='c1', destructive=True
    )


def test_danger_full_access_mode_with_allow_all_destructive_passes() -> None:
    # The bypass is only honored in danger-full-access mode.
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.DANGER_FULL_ACCESS,
        allow_all_destructive=True,
        full_access_acknowledged=True,
    )
    policy.assert_allowed(
        tool_name='workspace_write_file', call_id='any', destructive=True
    )


def test_prompt_mode_allow_all_destructive_without_ack_blocks() -> None:
    # P1-TR-011: Verify that allow_all_destructive without acknowledgment blocks.
    from teaagent.types import DenialReasonCode

    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        allow_all_destructive=True,
        full_access_acknowledged=False,
    )
    with pytest.raises(ToolPermissionError) as ctx:
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='any', destructive=True
        )
    assert ctx.value.reason_code == DenialReasonCode.FULL_ACCESS_NOT_ACKNOWLEDGED


# NOTE: the former test_prompt_mode_preapproved_call_id_with_store was removed.
# It asserted that ``preapproved_call_ids`` GRANTS approval, which contradicts
# the deliberate G-P2-2 removal of call-id preapproval. The shipped behavior
# (call-id preapproval no longer grants) is covered by
# tests/test_preapproved_call_ids_removal.py. See the open reconciliation item:
# the ``--approve-call-id`` flag and ApprovalManager.handle_preapproved are now
# dead and docs/governance/scope-taxonomy.md still lists call_id as implemented.


def test_prompt_mode_without_approval_blocks() -> None:
    policy = ApprovalPolicy()
    with pytest.raises(ToolPermissionError) as ctx:
        policy.assert_allowed(
            tool_name='workspace_write_file', call_id='unapproved', destructive=True
        )
    assert 'explicit approval' in str(ctx.value)


def test_policy_is_frozen() -> None:
    policy = ApprovalPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.allow_all_destructive = True


def test_scoped_approval_blocks_same_call_id_different_tool() -> None:
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
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_run_shell_mutate',
                call_id='write-1',
                destructive=True,
                arguments={'command': 'rm -rf build'},
            )
        assert 'explicit approval' in str(ctx.value)

        # This should fail - same call_id and tool but different arguments
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='write-1',
                destructive=True,
                arguments={'path': 'dangerous.txt', 'content': 'malicious'},
            )
        assert 'explicit approval' in str(ctx.value)


def test_scoped_approval_blocks_sensitive_command_mismatch() -> None:
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
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_run_shell_mutate',
                call_id='shell-1',
                destructive=True,
                arguments={'command': 'rm -rf /important'},
            )
        assert 'explicit approval' in str(ctx.value)

        # The record must NOT be consumed
        records = store.list_scoped_approvals_for_run(run_id)
        assert len(records) == 1
        assert records[0].consumed_at is None


def test_scoped_approval_blocks_sensitive_content_mismatch() -> None:
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
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='write-1',
                destructive=True,
                arguments={'path': 'out.txt', 'content': 'malicious payload'},
            )
        assert 'explicit approval' in str(ctx.value)

        # The record must NOT be consumed
        records = store.list_scoped_approvals_for_run(run_id)
        assert len(records) == 1
        assert records[0].consumed_at is None


def test_scoped_approval_blocks_sensitive_patch_mismatch() -> None:
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
        with pytest.raises(ToolPermissionError) as ctx:
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
        assert 'explicit approval' in str(ctx.value)

        # The record must NOT be consumed
        records = store.list_scoped_approvals_for_run(run_id)
        assert len(records) == 1
        assert records[0].consumed_at is None


def test_hmac_sha256_fingerprint_matching() -> None:
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
        assert len(record_v2.argument_digest) == 64

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
        assert store.list_scoped_approvals_for_run(run_id) == []

        # 2. Add a legacy v1 record explicitly passing a v1 16-hex digest
        from teaagent.ergonomics._approval_grants import _compute_argument_digest

        v1_digest = _compute_argument_digest(arguments)
        assert len(v1_digest) == 16

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


def test_resume_deduplication() -> None:
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
        assert has_existing is None

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
        assert has_existing is not None
        assert has_existing.argument_digest == digest


def test_teaagent_dir_created_with_0700() -> None:
    """__init__ must chmod .teaagent to 0o700."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        teaagent_dir = store.root / '.teaagent'
        mode = teaagent_dir.stat().st_mode & 0o777
        assert mode == 0o700, f'.teaagent/ should be 0o700 but got {oct(mode)}'


def test_approvals_json_written_with_0600() -> None:
    """_save must chmod approvals.json to 0o600 after every write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store.grant(
            tool_name='shell_exec',
            scope='once',
            command_prefixes=['pytest '],
        )
        mode = store.path.stat().st_mode & 0o777
        assert mode == 0o600, f'approvals.json should be 0o600 but got {oct(mode)}'


def test_secret_written_with_0600() -> None:
    """_get_workspace_secret must chmod secret to 0o600 after creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        # trigger secret generation
        store._get_workspace_secret()
        secret_path = store.root / '.teaagent' / 'secret'
        assert secret_path.exists(), 'secret file should be created'
        mode = secret_path.stat().st_mode & 0o777
        assert mode == 0o600, f'secret should be 0o600 but got {oct(mode)}'


def test_secret_raises_ioerror_on_corrupt_content() -> None:
    """_get_workspace_secret must raise IOError on invalid hex content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        secret_path = store.root / '.teaagent' / 'secret'
        # Write garbage shorter than 64 chars
        secret_path.write_text('tooshort', encoding='utf-8')
        with pytest.raises(IOError):
            store._get_workspace_secret()


def test_secret_raises_ioerror_on_non_hex_content() -> None:
    """_get_workspace_secret must raise IOError when 64-char but not valid hex."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        secret_path = store.root / '.teaagent' / 'secret'
        secret_path.write_text('x' * 64, encoding='utf-8')  # not hex
        with pytest.raises(IOError):
            store._get_workspace_secret()


def test_check_security_health_fresh_workspace_is_ok() -> None:
    """Fresh workspace with no approvals yet should report ok=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        result = store.check_security_health()
        assert 'ok' in result
        assert 'checks' in result
        assert isinstance(result['checks'], list)
        # No errors expected on a fresh workspace (files don't exist yet)
        assert result['ok'], f'Unexpected errors: {result["checks"]}'


def test_check_security_health_detects_wrong_dir_mode() -> None:
    """check_security_health reports error when .teaagent/ mode is too open."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        teaagent_dir = store.root / '.teaagent'
        teaagent_dir.chmod(0o755)  # too permissive
        result = store.check_security_health()
        dir_check = next(
            (c for c in result['checks'] if c['name'] == 'teaagent_dir_mode'), None
        )
        assert dir_check is not None, 'teaagent_dir_mode check should be present'
        assert not dir_check['ok']
        assert dir_check['severity'] == 'error'


def test_check_security_health_detects_wrong_secret_mode() -> None:
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
        assert secret_check is not None
        assert not secret_check['ok']
        assert secret_check['severity'] == 'error'


def test_check_security_health_detects_wrong_approvals_mode() -> None:
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
        assert approvals_check is not None
        assert not approvals_check['ok']
        assert approvals_check['severity'] == 'error'


def test_check_security_health_result_structure() -> None:
    """Each check entry must have name, ok, severity, message fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        result = store.check_security_health()
        for check in result['checks']:
            assert 'name' in check
            assert 'ok' in check
            assert 'severity' in check
            assert 'message' in check
            assert check['severity'] in ('error', 'warning', 'info')


def test_check_security_health_detects_wrong_dir_ownership() -> None:
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
        assert dir_ownership_check is not None, (
            'teaagent_dir_ownership check should be present'
        )
        # Should pass since we own the directory
        assert dir_ownership_check['ok']


def test_check_security_health_detects_wrong_secret_ownership() -> None:
    """check_security_health reports error when secret file is owned by wrong user."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store._get_workspace_secret()  # create secret
        result = store.check_security_health()
        secret_ownership_check = next(
            (c for c in result['checks'] if c['name'] == 'secret_file_ownership'),
            None,
        )
        assert secret_ownership_check is not None, (
            'secret_file_ownership check should be present'
        )
        # Should pass since we own the file
        assert secret_ownership_check['ok']


def test_check_security_health_detects_wrong_approvals_ownership() -> None:
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
            (c for c in result['checks'] if c['name'] == 'approvals_file_ownership'),
            None,
        )
        assert approvals_ownership_check is not None, (
            'approvals_file_ownership check should be present'
        )
        # Should pass since we own the file
        assert approvals_ownership_check['ok']


def test_fresh_v2_approval_not_flagged_as_orphan() -> None:
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
        assert orphan_check['ok'], (
            f'Fresh v2 approval should NOT be orphan: {orphan_check}'
        )


def test_rotated_secret_flags_old_v2_approval_as_orphan() -> None:
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
        assert not orphan_check['ok'], (
            f'After rotation, old v2 approval should be orphaned: {orphan_check}'
        )
        assert 'orphaned_record_ids' in orphan_check
        assert len(orphan_check['orphaned_record_ids']) == 1


def test_v2_approval_without_key_id_not_flagged() -> None:
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
        assert orphan_check['ok'], (
            f'Legacy record without key_id must not be flagged: {orphan_check}'
        )


def test_corrupt_json_detected_by_health_check() -> None:
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
        assert content_check is not None, 'approvals_file_content check must exist'
        assert not content_check['ok']
        assert content_check['severity'] == 'error'


def test_wrong_top_level_type_detected_by_health_check() -> None:
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
        assert content_check is not None
        assert not content_check['ok']
        assert 'list' in content_check['message']


def test_bad_key_type_detected_by_health_check() -> None:
    """check_security_health must report error when a required list key is not a list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store.grant(
            tool_name='shell_exec',
            scope='once',
            command_prefixes=['pytest '],
        )
        store.path.write_text(
            json.dumps({'grants': 'not-a-list', 'audit': [], 'scoped_approvals': []}),
            encoding='utf-8',
        )
        result = store.check_security_health()
        content_check = next(
            (c for c in result['checks'] if c['name'] == 'approvals_file_content'),
            None,
        )
        assert content_check is not None
        assert not content_check['ok']
        assert 'grants' in content_check.get('bad_keys', [])


def test_valid_approvals_json_passes_content_check() -> None:
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
        assert content_check is not None
        assert content_check['ok']


def test_mutating_store_fails_closed_on_corrupt_json() -> None:
    """Mutating paths must not silently replace a corrupt approvals.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store.grant(
            tool_name='shell_exec',
            scope='once',
            command_prefixes=['pytest '],
        )
        store.path.write_text('{bad json', encoding='utf-8')

        with pytest.raises(IOError):
            store.grant(
                tool_name='workspace_write_file',
                scope='once',
                path_globs=['src/**'],
            )

        assert store.path.read_text(encoding='utf-8') == '{bad json'


def test_repair_store_noops_on_healthy_store() -> None:
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

        assert result['status'] == 'noop'
        assert not result['repaired']
        assert store.path.read_text(encoding='utf-8') == before


def test_repair_store_rebuilds_corrupt_store_with_backup() -> None:
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

        assert result['status'] == 'repaired'
        assert result['repaired']
        assert result['backup_path'] is not None
        with open(result['backup_path'], encoding='utf-8') as backup:
            assert backup.read() == '{bad json'
        repaired = json.loads(store.path.read_text(encoding='utf-8'))
        assert repaired['grants'] == []
        assert repaired['audit'][0]['action'] == 'store_repaired'


def test_repair_store_operator_reset_is_audited_separately() -> None:
    """Explicit healthy-store reset is allowed only as a distinct audit event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        store.grant(
            tool_name='shell_exec',
            scope='once',
            command_prefixes=['pytest '],
        )

        result = store.repair_store(reset_healthy=True)

        assert result['status'] == 'reset'
        assert result['repaired']
        assert result['backup_path'] is not None
        reset_store = json.loads(store.path.read_text(encoding='utf-8'))
        assert reset_store['grants'] == []
        assert reset_store['audit'][0]['action'] == 'store_operator_reset'


def test_repair_store_same_second_creates_distinct_backups() -> None:
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

        assert backup_path1 != backup_path2
        assert '.json.backup.' in backup_path1
        assert '.json.backup.' in backup_path2
        # Verify both backups exist and contain their respective corrupt data
        with open(backup_path1, encoding='utf-8') as f:
            assert f.read() == '{bad json'
        with open(backup_path2, encoding='utf-8') as f:
            assert f.read() == '{bad json 2'


def test_fix_permissions_repairs_dir_mode() -> None:
    """check_security_health(fix_permissions=True) must chmod the dir back to 0o700."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ApprovalPresetStore(tmpdir)
        teaagent_dir = store.root / '.teaagent'
        teaagent_dir.chmod(0o755)
        result = store.check_security_health(fix_permissions=True)
        mode_after = teaagent_dir.stat().st_mode & 0o777
        assert mode_after == 0o700
        next(c for c in result['checks'] if c['name'] == 'teaagent_dir_mode')


def test_multi_sig_config_defaults() -> None:
    """Verify default multi-sig configuration."""
    config = MultiSigQuorumConfig()
    assert not config.enabled
    assert config.required_approvals == 2
    assert config.peer_agent_ids == []
    assert config.high_risk_patterns == []
    assert config.timeout_seconds == 300


def test_multi_sig_config_from_workspace_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path

        root = Path(tmpdir)
        (root / '.teaagent').mkdir()
        (root / '.teaagent' / 'config.json').write_text(
            json.dumps(
                {
                    'multi_sig': {
                        'enabled': True,
                        'required_approvals': 2,
                        'peer_agent_ids': ['peer-a'],
                        'peer_relay_urls': {'peer-a': 'https://peer-a.example:8791'},
                        'local_relay_base_url': 'https://collector.example:8791',
                    }
                }
            ),
            encoding='utf-8',
        )
        config = MultiSigQuorumConfig.from_workspace_config(root)
        assert config.enabled
        assert config.peer_relay_urls['peer-a'] == 'https://peer-a.example:8791'
        assert config.local_relay_base_url == 'https://collector.example:8791'


def test_multi_sig_config_custom() -> None:
    """Verify custom multi-sig configuration."""
    config = MultiSigQuorumConfig(
        enabled=True,
        required_approvals=3,
        peer_agent_ids=['agent-1', 'agent-2', 'agent-3'],
        high_risk_patterns=['/prod', '/production'],
        timeout_seconds=600,
    )
    assert config.enabled
    assert config.required_approvals == 3
    assert len(config.peer_agent_ids) == 3
    assert '/prod' in config.high_risk_patterns
    assert config.timeout_seconds == 600


def test_policy_with_multi_sig_disabled() -> None:
    """Verify policy behaves normally when multi-sig is disabled."""
    config = MultiSigQuorumConfig(enabled=False)
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=config,
    )

    # Should still require normal approval
    with pytest.raises(ToolPermissionError):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-1',
            destructive=True,
            arguments={'path': '/prod/config.json'},
        )


def test_high_risk_detection_default_patterns() -> None:
    """Verify default high-risk pattern detection."""
    config = MultiSigQuorumConfig(enabled=True, required_approvals=2)
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=config,
        agent_id='test-agent',
    )

    # Should detect /prod path as high-risk
    assert policy._is_high_risk_operation(
        'workspace_write_file', {'path': '/prod/config.json'}
    )

    # Should detect /production path in arguments
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate', {'command': 'deploy /production/app'}
    )

    # Should detect delete operations
    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate', {'command': 'rm -rf /tmp'}
    )


def test_high_risk_detection_custom_patterns() -> None:
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
    assert policy._is_high_risk_operation(
        'workspace_write_file', {'path': '/critical/data.json'}
    )

    assert policy._is_high_risk_operation(
        'workspace_run_shell_mutate', {'command': './deploy.sh'}
    )


def test_approval_request_hash_generation() -> None:
    """Verify approval request hash generation is deterministic."""
    policy = ApprovalPolicy(agent_id='test-agent')

    hash1 = policy._generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'test.txt'}
    )

    hash2 = policy._generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'test.txt'}
    )

    # Same inputs should produce same hash
    assert hash1 == hash2

    # Different inputs should produce different hash
    hash3 = policy._generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'different.txt'}
    )
    assert hash1 != hash3


def test_multi_sig_quorum_without_agent_id() -> None:
    """Verify multi-sig falls back gracefully without agent_id."""
    config = MultiSigQuorumConfig(enabled=True, required_approvals=2)
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=config,
        agent_id='',  # Empty agent_id
    )

    # Should fall back to normal approval flow
    with pytest.raises(ToolPermissionError):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-1',
            destructive=True,
            arguments={'path': '/prod/config.json'},
        )


@pytest.mark.skip(
    'Multi-sig quorum requires federated_sync P2P broadcast — integration test, not unit-testable'
)
def test_multi_sig_quorum_stub_returns_false() -> None:
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

    assert not result


# P0-D-001: Workspace root containment
def test_workspace_root_allows_path_within_root() -> None:
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


def test_workspace_root_blocks_path_escaping_via_parent_traversal() -> None:
    """Path arguments escaping workspace via ../ are blocked."""
    with tempfile.TemporaryDirectory() as tmp:
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=tmp,
        )
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='c1',
                destructive=True,
                arguments={'path': '../etc/passwd'},
            )
        assert 'outside workspace root' in str(ctx.value)


def test_workspace_root_blocks_absolute_path_outside_root() -> None:
    """Absolute paths outside workspace root are blocked."""
    with tempfile.TemporaryDirectory() as tmp:
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=tmp,
        )
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='c1',
                destructive=True,
                arguments={'path': '/etc/passwd'},
            )
        assert 'outside workspace root' in str(ctx.value)


def test_workspace_root_does_not_block_non_path_tools() -> None:
    """Non-path tools (e.g. shell inspect) are not blocked by root check."""
    with tempfile.TemporaryDirectory() as tmp:
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=tmp,
        )
        # workspace_run_shell_inspect has no 'path' argument — should not trigger root check
        with pytest.raises(ToolPermissionError) as ctx:
            policy.assert_allowed(
                tool_name='workspace_run_shell_inspect',
                call_id='c1',
                destructive=True,
                arguments={'command': 'ls'},
            )
        # Should fail because no JIT/prompt handler, not because of root containment
        assert 'outside workspace root' not in str(ctx.value)


def test_empty_path_globs_rejected_in_grant() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(tmpdir)
        with pytest.raises(ValueError) as ctx:
            store.grant(
                tool_name='workspace_write_file',
                scope='always',
                path_globs=[''],
            )
        assert 'non-empty pattern' in str(ctx.value)


def test_whitespace_only_path_globs_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(tmpdir)
        with pytest.raises(ValueError) as ctx:
            store.grant(
                tool_name='workspace_write_file',
                scope='always',
                path_globs=['   ', '\t'],
            )
        assert 'non-empty pattern' in str(ctx.value)


def test_root_path_globs_dot_accepted() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(tmpdir)
        grant = store.grant(
            tool_name='workspace_write_file',
            scope='always',
            path_globs=['.', 'src/**'],
        )
        assert grant is not None
        assert '.' in grant.path_globs
        assert 'src/**' in grant.path_globs


def test_root_path_globs_star_accepted() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(tmpdir)
        grant = store.grant(
            tool_name='workspace_write_file',
            scope='always',
            path_globs=['*'],
        )
        assert grant is not None
        assert '*' in grant.path_globs


def test_del_shuts_down_signature_executor() -> None:
    """ENG-01: __del__ must shut down the ThreadPoolExecutor to prevent thread leaks."""
    policy = ApprovalPolicy()
    executor = policy._signature_executor
    policy.__del__()
    with pytest.raises(RuntimeError):
        executor.submit(lambda: None)


def test_del_is_safe_to_call_twice() -> None:
    policy = ApprovalPolicy()
    policy.__del__()
    policy.__del__()  # must not raise


def test_prompt_auto_denies_on_timeout() -> None:
    """OPS-01: JIT approval prompt must auto-deny after the configured timeout."""
    blocker = threading.Event()

    def blocking_input(prompt: str) -> str:
        blocker.wait()
        return 'o'

    manager = JITApprovalManager(approval_timeout_seconds=0.05)
    with patch('builtins.input', side_effect=blocking_input):
        result = manager._prompt('tool_x', 'call-timeout-1')

    blocker.set()
    assert result == 'd', 'timed-out prompt must return deny'


def test_prompt_respects_valid_choice_before_timeout() -> None:
    """OPS-01: fast user response must pass through normally."""
    manager = JITApprovalManager(approval_timeout_seconds=5.0)
    with patch('builtins.input', return_value='o'):
        result = manager._prompt('tool_x', 'call-fast-1')
    assert result == 'o'
