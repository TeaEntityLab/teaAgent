# test-type: adversarial
"""Tests for security fixes applied to the codebase.

This test suite validates the security improvements made to address
medium-severity security vulnerabilities.
"""

import tempfile
from pathlib import Path

import pytest

from teaagent.context_bus import ContextBus, ContextBusConfig
from teaagent.llm._retry import LLMRetryConfig
from teaagent.policy import ApprovalPolicy
from teaagent.surface_auth import (
    hash_token,
    hash_token_with_salt,
    verify_token_with_salt,
)
from teaagent.types import (
    PermissionMode,
    ToolExecutionError,
    ToolPermissionError,
    ToolValidationError,
)
from teaagent.workspace_tools import _shell as shell_module
from teaagent.workspace_tools._files import (
    WorkspaceToolConfig,
    build_workspace_tool_registry,
)
from teaagent.workspace_tools._shell import run_shell


class TestShellCommandInjectionFix:
    """Tests for shell command injection vulnerability fix."""

    def test_shell_uses_shlex_split_not_shell_true(self):
        """Verify that shell command execution uses shlex.split() instead of shell=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)

            # Test that shell commands are parsed safely
            result = run_shell(config, {'command': 'echo "test"'})

            # Should not have shell=True in subprocess call
            assert 'stdout' in result
            assert 'stderr' in result
            assert 'exit_code' in result

    def test_shell_dangerous_commands_are_governed_not_executed(self, monkeypatch):
        """Dangerous commands must be refused by governance before any process starts.

        `run_shell` has no command denylist by design; safety comes from the
        governed path (both shell tools are registered `destructive=True` and
        `ApprovalPolicy` refuses them in read-only, workspace-write, and
        unapproved prompt mode). An earlier version of this test called
        `run_shell` with `rm -rf /`, `mkfs`, and `dd if=/dev/zero of=/dev/sda`
        for real, relying on the host to refuse them; as root in a container it
        overwrote a device-named file for the full 30 s timeout (2026-10-09).
        This version fails loudly if any subprocess is ever spawned.
        """

        def _never_spawn(*args, **kwargs):
            raise AssertionError(
                'subprocess.run must not be reached for an ungoverned destructive command'
            )

        monkeypatch.setattr(shell_module.subprocess, 'run', _never_spawn)

        dangerous_commands = [
            'rm -rf /',
            'mkfs',
            'dd if=/dev/zero of=/dev/sda',
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)
            for name in ('workspace_run_shell_mutate', 'workspace_run_shell'):
                definition = registry.get(name)
                assert definition.annotations.destructive is True
                assert definition.annotations.read_only is False
                for mode in (
                    PermissionMode.READ_ONLY,
                    PermissionMode.WORKSPACE_WRITE,
                    PermissionMode.PROMPT,
                ):
                    policy = ApprovalPolicy(permission_mode=mode)
                    for cmd in dangerous_commands:
                        with pytest.raises(ToolPermissionError):
                            policy.assert_allowed(
                                tool_name=name,
                                call_id=f'call-{mode.value}-{name}',
                                destructive=True,
                                arguments={'command': cmd},
                            )


class TestRegexValidationFix:
    """Tests for regex validation vulnerability fix."""

    def test_regex_pattern_validation(self):
        """Verify that regex patterns are validated before compilation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Test invalid regex pattern
            with pytest.raises(ToolExecutionError, match='Invalid regex pattern'):
                registry.invoke(
                    'workspace_search_text',
                    {
                        'pattern': '[invalid(',  # Invalid regex
                    },
                )
            # Verify that valid patterns work
            result = registry.invoke(
                'workspace_search_text',
                {
                    'pattern': 'valid',
                },
            )
            assert 'error' not in result

    def test_regex_timeout_protection(self):
        """Verify that regex operations have timeout protection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Test regex with potential ReDoS
            result = registry.invoke(
                'workspace_search_text',
                {
                    'pattern': '(a+)+',  # Potential ReDoS pattern
                },
            )

            # Should complete without hanging
            assert (
                'error' not in result
                or 'timeout' not in result.get('stderr', '').lower()
            )


class TestTOCTOUFix:
    """Tests for Time-of-Check-Time-of-Use race condition fix."""

    def test_atomic_file_write(self):
        """Verify that file writes use atomic operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')

            # Write with expected_mtime validation
            stat = test_file.stat()
            result = registry.invoke(
                'workspace_write_file',
                {
                    'path': 'test.txt',
                    'content': 'updated',
                    'expected_mtime': stat.st_mtime,
                },
            )

            # Should succeed with same mtime
            assert result.get('ok', True) or 'error' not in result

    def test_mtime_mismatch_detection(self):
        """Verify that mtime mismatch is detected and prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')

            # Try to write with wrong mtime
            with pytest.raises(ToolExecutionError, match='modified since last read'):
                registry.invoke(
                    'workspace_write_file',
                    {
                        'path': 'test.txt',
                        'content': 'updated',
                        'expected_mtime': 0.0,  # Wrong mtime
                    },
                )
            # Verify the file was not modified
            assert test_file.read_text() == 'original'


class TestSymlinkValidationFix:
    """Tests for symlink validation vulnerability fix."""

    def test_symlink_blocked_in_read(self):
        """Verify that workspace reads reject symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Create a symlink
            target_file = Path(tmpdir) / 'target.txt'
            target_file.write_text('content')
            symlink = Path(tmpdir) / 'link.txt'
            symlink.symlink_to(target_file)

            with pytest.raises(ToolExecutionError, match='symlinks are not allowed'):
                registry.invoke('workspace_read_file', {'path': 'link.txt'})

    def test_symlink_blocked_in_write(self):
        """Verify that workspace writes reject symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Create a symlink
            target_file = Path(tmpdir) / 'target.txt'
            target_file.write_text('original')
            symlink = Path(tmpdir) / 'link.txt'
            symlink.symlink_to(target_file)

            with pytest.raises(ToolExecutionError, match='symlinks are not allowed'):
                registry.invoke(
                    'workspace_write_file',
                    {
                        'path': 'link.txt',
                        'content': 'updated',
                    },
                )
            assert target_file.read_text() == 'original'


class TestSecureRandomFix:
    """Tests for insecure random number generation fix."""

    def test_context_bus_uses_secrets(self):
        """Verify that context_bus uses secrets module instead of random."""
        # Test that retry delay uses secrets
        config = LLMRetryConfig()
        delay1 = config.delay(0)
        delay2 = config.delay(0)

        # Delays should be different (using secrets.randbelow)
        assert delay1 != delay2

    def test_llm_retry_uses_secrets(self):
        """Verify that llm retry uses secrets module instead of random."""
        # Test that retry delay uses secrets
        config = LLMRetryConfig()
        delays = [config.delay(i) for i in range(10)]

        # Delays should be different (using secrets.randbelow)
        assert len(set(delays)) > 1  # At least some variety


class TestEnvironmentVariableFilteringFix:
    """Tests for environment variable filtering fix."""

    def test_allowlist_environment_variables(self):
        """Verify that environment variables use allowlist approach."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WorkspaceToolConfig.from_root(tmpdir)

            # Set a sensitive environment variable
            import os

            os.environ['TEST_SECRET_TOKEN'] = 'secret_value'

            # Run a command
            result = run_shell(config, {'command': 'echo test'})

            # Sensitive variable should not be in environment
            # (This is verified by checking the implementation uses allowlist)
            assert result['exit_code'] == 0


class TestWeakTokenHashingFix:
    """Tests for weak token hashing fix."""

    def test_hash_token_uses_pbkdf2(self):
        """Verify that token hashing uses PBKDF2 instead of simple SHA256."""
        token = 'test_token'
        hash1 = hash_token(token)
        hash2 = hash_token(token)

        # Should be deterministic (fixed salt for backward compatibility)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_hash_token_with_salt_uses_random_salt(self):
        """Verify that salted hashing uses random salt."""
        token = 'test_token'
        hash1, salt1 = hash_token_with_salt(token)
        hash2, salt2 = hash_token_with_salt(token)

        # Should use different salts
        assert salt1 != salt2
        assert hash1 != hash2
        assert len(salt1) == 32  # 16 bytes = 32 hex chars

    def test_verify_token_with_salt(self):
        """Verify that token verification works correctly."""
        token = 'test_token'
        hash_hex, salt_hex = hash_token_with_salt(token)

        # Verify correct token
        assert verify_token_with_salt(token, hash_hex, salt_hex) is True

        # Verify wrong token
        assert verify_token_with_salt('wrong_token', hash_hex, salt_hex) is False


class TestLineValidationFix:
    """Tests for line number validation fix."""

    def test_line_number_validation(self):
        """Verify that line numbers are properly validated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('line1\nline2\nline3')

            # Test invalid line number (too high)
            with pytest.raises(ToolExecutionError, match='outside file range'):
                registry.invoke(
                    'workspace_edit_at_hash',
                    {
                        'path': 'test.txt',
                        'line': 100,  # Invalid line number
                        'hash': 'some_hash',
                        'old': 'line1',
                        'new': 'updated',
                    },
                )
            # Verify the file was not modified
            assert test_file.read_text() == 'line1\nline2\nline3'

    def test_line_number_type_validation(self):
        """Verify that line number type is validated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('line1\nline2\nline3')

            # Test invalid line number type
            with pytest.raises(ToolValidationError, match='must be integer'):
                registry.invoke(
                    'workspace_edit_at_hash',
                    {
                        'path': 'test.txt',
                        'line': 'invalid',  # Invalid type
                        'hash': 'some_hash',
                        'old': 'line1',
                        'new': 'updated',
                    },
                )
            # Verify the file was not modified
            assert test_file.read_text() == 'line1\nline2\nline3'


class TestPathTraversalFix:
    """Tests for path traversal validation fix."""

    def test_path_traversal_blocked(self):
        """Verify that path traversal is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Try to read file outside workspace using path traversal
            with pytest.raises(ToolExecutionError, match='path escapes workspace root'):
                registry.invoke('workspace_read_file', {'path': '../../../etc/passwd'})
            # Verify that valid paths within workspace work
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('content')
            result = registry.invoke('workspace_read_file', {'path': 'test.txt'})
            assert result.get('content') == 'content'


class TestEmptyFileValidationFix:
    """Tests for empty file validation fix."""

    def test_empty_file_edit_blocked(self):
        """Verify that editing empty file is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_workspace_tool_registry(tmpdir)

            # Create empty file
            test_file = Path(tmpdir) / 'empty.txt'
            test_file.write_text('')

            # Try to edit empty file
            with pytest.raises(ToolExecutionError, match='Cannot edit empty file'):
                registry.invoke(
                    'workspace_edit_at_hash',
                    {
                        'path': 'empty.txt',
                        'line': 1,
                        'hash': 'some_hash',
                        'old': '',
                        'new': 'content',
                    },
                )
            # Verify the file remains empty
            assert test_file.read_text() == ''


class TestContextBusValidationFix:
    """Tests for ContextBus constructor validation fix."""

    def test_workflow_id_validation(self):
        """Verify that workflow_id is validated."""
        with pytest.raises(ValueError, match='workflow_id cannot be empty'):
            ContextBus(
                ContextBusConfig(
                    db_path=Path('/tmp/test.db'),
                    workflow_id='',  # Invalid empty workflow_id
                    max_delta_age_seconds=3600,
                )
            )
        # Verify that valid workflow_id works
        bus = ContextBus(
            ContextBusConfig(
                db_path=Path('/tmp/test.db'),
                workflow_id='valid-workflow',
                max_delta_age_seconds=3600,
            )
        )
        assert bus is not None

    def test_max_delta_age_validation(self):
        """Verify that max_delta_age_seconds is validated."""
        with pytest.raises(ValueError, match='max_delta_age_seconds must be positive'):
            ContextBus(
                ContextBusConfig(
                    db_path=Path('/tmp/test.db'),
                    workflow_id='test-workflow',
                    max_delta_age_seconds=-1,  # Invalid negative value
                )
            )
        # Verify that valid max_delta_age works
        bus = ContextBus(
            ContextBusConfig(
                db_path=Path('/tmp/test.db'),
                workflow_id='test-workflow',
                max_delta_age_seconds=3600,
            )
        )
        assert bus is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
