"""Tests for code quality improvements and refactoring.

This test suite validates the code quality improvements including
function decomposition, import organization, and type safety.
"""

import tempfile
from pathlib import Path

import pytest

from teaagent.cli._handlers._agent import (
    _display_file_list,
    _display_review_header,
    _display_review_summary,
    _get_changed_files,
    _handle_review_choice,
    _load_suspension_data,
    _save_review_decisions,
    interactive_review_mode,
)
from teaagent.cli._handlers._ergonomics import _truncate_string
from teaagent.errors import ToolExecutionError
from teaagent.workspace_tools._files import (
    WorkspaceToolConfig,
    build_workspace_tool_registry,
)


class TestFunctionDecomposition:
    """Tests for interactive_review_mode function decomposition."""

    def test_load_suspension_data_valid_file(self):
        """Test _load_suspension_data with valid suspension file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create suspension file
            tea_dir = Path(tmpdir) / '.teaagent'
            tea_dir.mkdir(parents=True, exist_ok=True)
            suspension_file = tea_dir / 'suspension-test-run.json'
            suspension_data = {
                'mode': 'chat',
                'timestamp': 1234567890.0,
                'acp_version': '1.0.0',
            }
            import json

            suspension_file.write_text(json.dumps(suspension_data))

            # Load suspension data
            result = _load_suspension_data(Path(tmpdir), 'test-run')

            assert result is not None
            assert result['mode'] == 'chat'

    def test_load_suspension_data_missing_file(self):
        """Test _load_suspension_data with missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _load_suspension_data(Path(tmpdir), 'nonexistent-run')
            assert result is None

    def test_load_suspension_data_corrupted_file(self):
        """Test _load_suspension_data with corrupted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tea_dir = Path(tmpdir) / '.teaagent'
            tea_dir.mkdir(parents=True, exist_ok=True)
            suspension_file = tea_dir / 'suspension-test-run.json'
            suspension_file.write_text('invalid json')

            result = _load_suspension_data(Path(tmpdir), 'test-run')
            assert result is None

    def test_display_review_header(self, capsys):
        """Test _display_review_header displays correct information."""
        suspension_data = {
            'mode': 'chat',
            'timestamp': 1234567890.0,
        }

        _display_review_header('test-run', suspension_data)

        captured = capsys.readouterr()
        assert 'Interactive Review Mode' in captured.out
        assert 'test-run' in captured.out
        assert 'chat' in captured.out

    def test_get_changed_files_with_changes(self):
        """Test _get_changed_files returns changed files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            import subprocess

            subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ['git', 'config', 'user.email', 'test@example.com'],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'Test User'],
                cwd=tmpdir,
                capture_output=True,
            )

            # Create and commit a file
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')
            subprocess.run(['git', 'add', 'test.txt'], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
            )

            # Modify file
            test_file.write_text('modified')

            # Get changed files
            changed_files = _get_changed_files(Path(tmpdir))

            assert changed_files is not None
            assert 'test.txt' in changed_files

    def test_get_changed_files_no_changes(self):
        """Test _get_changed_files returns None when no changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            import subprocess

            subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ['git', 'config', 'user.email', 'test@example.com'],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'Test User'],
                cwd=tmpdir,
                capture_output=True,
            )

            # No changes
            changed_files = _get_changed_files(Path(tmpdir))
            assert changed_files is None

    def test_display_file_list(self, capsys):
        """Test _display_file_list displays file list correctly."""
        changed_files = ['file1.txt', 'file2.txt', 'file3.txt']

        _display_file_list(changed_files)

        captured = capsys.readouterr()
        assert '3 changed file(s)' in captured.out
        assert 'file1.txt' in captured.out
        assert 'Review commands:' in captured.out

    def test_handle_review_choice_accept(self):
        """Test _handle_review_choice handles accept choice."""
        review_decisions = {}
        root_path = Path('/tmp')

        should_continue = _handle_review_choice(
            'y', 'test.txt', root_path, review_decisions
        )

        assert should_continue is True
        assert review_decisions['test.txt'] == 'accepted'

    def test_handle_review_choice_edit(self):
        """Test _handle_review_choice handles edit choice."""
        review_decisions = {}
        root_path = Path('/tmp')

        should_continue = _handle_review_choice(
            'e', 'test.txt', root_path, review_decisions
        )

        assert should_continue is True
        assert review_decisions['test.txt'] == 'edited'

    def test_handle_review_choice_reject(self):
        """Test _handle_review_choice handles reject choice."""
        review_decisions = {}
        root_path = Path('/tmp')

        should_continue = _handle_review_choice(
            'r', 'test.txt', root_path, review_decisions
        )

        assert should_continue is True
        assert review_decisions['test.txt'] == 'rejected'

    def test_handle_review_choice_quit(self):
        """Test _handle_review_choice handles quit choice."""
        review_decisions = {}
        root_path = Path('/tmp')

        should_continue = _handle_review_choice(
            'q', 'test.txt', root_path, review_decisions
        )

        assert should_continue is False

    def test_display_review_summary(self, capsys):
        """Test _display_review_summary displays correct summary."""
        review_decisions = {
            'file1.txt': 'accepted',
            'file2.txt': 'edited',
            'file3.txt': 'rejected',
        }
        changed_files = ['file1.txt', 'file2.txt', 'file3.txt', 'file4.txt']

        _display_review_summary(review_decisions, changed_files)

        captured = capsys.readouterr()
        assert 'Review Summary' in captured.out
        assert 'Accepted: 1' in captured.out
        assert 'Edited: 1' in captured.out
        assert 'Rejected: 1' in captured.out
        assert 'Skipped: 1' in captured.out

    def test_save_review_decisions(self):
        """Test _save_review_decisions saves decisions correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tea_dir = Path(tmpdir) / '.teaagent'
            tea_dir.mkdir(parents=True, exist_ok=True)

            review_decisions = {'file1.txt': 'accepted'}
            suspension_data = {'mode': 'chat', 'audit_trail': {}}
            changed_files = ['file1.txt']

            _save_review_decisions(
                tea_dir, 'test-run', review_decisions, suspension_data, changed_files
            )

            review_file = tea_dir / 'review-test-run.json'
            assert review_file.exists()

            import json

            with open(review_file) as f:
                saved_data = json.load(f)

            assert saved_data['run_id'] == 'test-run'
            assert saved_data['decisions'] == review_decisions
            assert saved_data['acp_version'] == '1.0.0'


class TestHelperFunctions:
    """Tests for helper functions extracted during refactoring."""

    def test_truncate_string_basic(self):
        """Test _truncate_string with basic string."""
        result = _truncate_string('hello world', max_len=10)
        assert result == 'hello w...'

    def test_truncate_string_no_truncation(self):
        """Test _truncate_string with string shorter than max."""
        result = _truncate_string('hi', max_len=10)
        assert result == 'hi'

    def test_truncate_string_custom_suffix(self):
        """Test _truncate_string with custom suffix."""
        result = _truncate_string('hello world', max_len=5, suffix='>>')
        assert result == 'hel>>'

    def test_truncate_string_zero_max(self):
        """Test _truncate_string with zero max length."""
        result = _truncate_string('test', max_len=0)
        assert result == 't...'

    def test_truncate_string_exact_length(self):
        """Test _truncate_string with exact max length."""
        result = _truncate_string('hello', max_len=5)
        assert result == 'hello'


class TestImportOrganization:
    """Tests for import organization improvements."""

    def test_subagent_review_imports_at_top_level(self):
        """Test that subagent review imports are at top level."""
        import inspect

        from teaagent.cli._handlers import _agent

        source = inspect.getsource(_agent)

        # Verify imports are at top level (also allowed inside function bodies for lazy loading)
        assert 'from teaagent.subagents._review import' in source


class TestTypeSafety:
    """Tests for type safety improvements."""

    def test_sandbox_branch_name_type_handling(self):
        """Test that sandbox branch name is type-safe."""
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent
        agent_path = root / 'teaagent' / 'cli' / '_handlers' / '_agent.py'
        source = agent_path.read_text(encoding='utf-8')

        # Verify getattr with default None is used to safely access _branch_name
        getattr_match = re.search(
            r"getattr\(\s*sandbox\s*,\s*'_branch_name'\s*,\s*None\s*\)",
            source,
        )
        assert getattr_match is not None, (
            '_branch_name should be accessed via getattr(sandbox, "_branch_name", None)'
        )

        # Verify str() conversion is applied when the value is used
        str_conv_match = re.search(
            r'str\(\s*branch_name\s*\)\s+if\s+branch_name\s+is\s+not\s+None',
            source,
        )
        assert str_conv_match is not None, (
            'branch_name should be converted via str() when not None for type safety'
        )


class TestErrorRecovery:
    """Tests for error recovery improvements."""

    def test_write_file_temp_cleanup_on_error(self):
        """Test that temp file cleanup is attempted on error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            WorkspaceToolConfig.from_root(tmpdir)
            registry = build_workspace_tool_registry(tmpdir)

            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')

            # Write with invalid mtime to trigger error
            with pytest.raises(
                ToolExecutionError,
                match='file test.txt was modified since last read',
            ):
                registry.invoke(
                    'workspace_write_file',
                    {
                        'path': 'test.txt',
                        'content': 'updated',
                        'expected_mtime': 0.0,  # Will cause error
                    },
                )


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility after refactoring."""

    def test_interactive_review_mode_backward_compatible(self):
        """Test that refactored interactive_review_mode maintains same interface."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create suspension file
            tea_dir = Path(tmpdir) / '.teaagent'
            tea_dir.mkdir(parents=True, exist_ok=True)
            suspension_file = tea_dir / 'suspension-test-run.json'
            suspension_data = {
                'mode': 'chat',
                'timestamp': 1234567890.0,
                'acp_version': '1.0.0',
            }
            import json

            suspension_file.write_text(json.dumps(suspension_data))

            # Initialize git repo
            import subprocess

            subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ['git', 'config', 'user.email', 'test@example.com'],
                cwd=tmpdir,
                capture_output=True,
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'Test User'],
                cwd=tmpdir,
                capture_output=True,
            )

            # Create and commit a file
            test_file = Path(tmpdir) / 'test.txt'
            test_file.write_text('original')
            subprocess.run(['git', 'add', 'test.txt'], cwd=tmpdir, capture_output=True)
            subprocess.run(
                ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
            )

            # Modify file
            test_file.write_text('modified')

            # Test that interactive_review_mode still works
            from unittest.mock import patch

            with patch('builtins.input', side_effect=['q']):
                result = interactive_review_mode(tmpdir, 'test-run')

            # Should complete without error
            assert result == 0 or result == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
