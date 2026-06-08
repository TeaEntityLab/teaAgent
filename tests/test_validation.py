"""Integration tests for LSP self-healing validation features."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.validation import (
    ValidationResult,
    ValidationRunner,
    detect_available_tools,
)
from teaagent.validation.profiles import (
    PROFILE_NAMES,
    ProfileCommandResult,
    ProfileValidationReport,
    _commands_for_profile,
)
from teaagent.validation.tool_detector import get_tool_command
from teaagent.validation.validators import ValidationError


class TestValidationError:
    """Test ValidationError data model."""

    def test_create_validation_error(self) -> None:
        """Test creating a validation error."""
        error = ValidationError(
            file_path='src/test.py',
            line_number=42,
            column=1,
            error_type='ruff',
            message="Undefined variable 'x'",
            severity='error',
        )

        assert error.file_path == 'src/test.py'
        assert error.line_number == 42
        assert error.column == 1
        assert error.error_type == 'ruff'
        assert error.message == "Undefined variable 'x'"
        assert error.severity == 'error'


class TestValidationResult:
    """Test ValidationResult data model."""

    def test_create_validation_result(self) -> None:
        """Test creating a validation result."""
        errors = [
            ValidationError(
                file_path='src/test.py',
                line_number=42,
                column=1,
                error_type='ruff',
                message='Error 1',
                severity='error',
            ),
        ]
        warnings = [
            ValidationError(
                file_path='src/test.py',
                line_number=50,
                column=1,
                error_type='ruff',
                message='Warning 1',
                severity='warning',
            ),
        ]

        result = ValidationResult(
            tool='ruff',
            passed=False,
            errors=errors,
            warnings=warnings,
            output='Validation output',
        )

        assert result.tool == 'ruff'
        assert result.passed is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.has_errors() is True
        assert result.has_warnings() is True

    def test_empty_result(self) -> None:
        """Test validation result with no issues."""
        result = ValidationResult(
            tool='mypy',
            passed=True,
            errors=[],
            warnings=[],
            output='No issues',
        )

        assert result.passed is True
        assert result.has_errors() is False
        assert result.has_warnings() is False


class TestLSPToolDetection:
    """Test LSP tool detection."""

    def test_detect_available_tools(self) -> None:
        """Test detecting available tools."""
        tools = detect_available_tools(Path('.'))
        # Just check that it returns a set of tool names
        assert isinstance(tools, set)
        # Tools should be from the known set
        known_tools = {'ruff', 'mypy', 'tsc', 'eslint'}
        assert tools.issubset(known_tools)


class TestValidationRunner:
    """Test ValidationRunner."""

    @pytest.fixture
    def temp_root(self) -> Iterator[Path]:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_runner_initialization(self, temp_root: Path) -> None:
        """Test validation runner initialization."""
        runner = ValidationRunner(root=temp_root, timeout=30)

        assert runner.root == temp_root.resolve()
        assert runner.timeout == 30

    def test_validate_file(self, temp_root: Path) -> None:
        """Test validating a file."""
        # Create a test Python file
        test_file = temp_root / 'test.py'
        test_file.write_text('x = 1\nprint(y)')  # Error: undefined variable

        with patch('shutil.which', return_value='/usr/bin/ruff'):
            runner = ValidationRunner(root=temp_root, timeout=30)
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="test.py:2:7: F821 Undefined variable 'y'",
                    stderr='',
                    returncode=1,
                )

                results = runner.validate_file(test_file)

                # Should have at least one result
                assert len(results) >= 1
                # Check that at least one tool ran
                assert any(r.tool in ['ruff', 'mypy', 'tsc', 'eslint'] for r in results)

    def test_timeout_handling(self, temp_root: Path) -> None:
        """Test timeout handling during validation."""
        test_file = temp_root / 'test.py'
        test_file.write_text('x = 1')

        with patch('shutil.which', return_value='/usr/bin/ruff'):
            runner = ValidationRunner(root=temp_root, timeout=0.1)
            with patch('subprocess.run') as mock_run:
                from subprocess import TimeoutExpired

                mock_run.side_effect = TimeoutExpired('ruff', 0.1)

                results = runner.validate_file(test_file)

                assert len(results) >= 1
                assert results[0].passed is False
                assert 'timed out' in results[0].output.lower()

    def test_tool_not_found(self, temp_root: Path) -> None:
        """Test when tool is not found."""
        test_file = temp_root / 'test.py'
        test_file.write_text('x = 1')

        with patch('teaagent.validation.tool_detector.shutil.which') as mock_which:
            mock_which.return_value = None

            runner = ValidationRunner(root=temp_root, timeout=30)
            results = runner.validate_file(test_file)

            # Should return empty results if no tools available
            assert len(results) == 0


class TestProfileCommands:
    """Tests for validation profile commands."""

    def test_commands_for_profile_fast(self) -> None:
        """Test fast profile includes ruff only."""
        commands = _commands_for_profile('fast')
        assert len(commands) == 1
        name, cmd = commands[0]
        assert name == 'ruff'
        assert 'check' in cmd
        assert '--quiet' in cmd

    def test_commands_for_profile_standard(self) -> None:
        """Test standard profile includes ruff and mypy."""
        commands = _commands_for_profile('standard')
        assert len(commands) == 2
        names = [n for n, _ in commands]
        assert 'ruff' in names
        assert 'mypy' in names

    def test_commands_for_profile_strict(self) -> None:
        """Test strict profile includes ruff, mypy, and pytest."""
        commands = _commands_for_profile('strict')
        assert len(commands) == 3
        names = [n for n, _ in commands]
        assert 'ruff' in names
        assert 'mypy' in names
        assert 'pytest' in names

    def test_profile_names_constant(self) -> None:
        """Test PROFILE_NAMES contains expected profiles."""
        assert 'fast' in PROFILE_NAMES
        assert 'standard' in PROFILE_NAMES
        assert 'strict' in PROFILE_NAMES


class TestProfileCommandResult:
    """Tests for ProfileCommandResult dataclass."""

    def test_defaults(self) -> None:
        """Test default values for skipped fields."""
        result = ProfileCommandResult(
            name='ruff', command=['ruff', 'check'], exit_code=0, stdout='', stderr=''
        )
        assert result.skipped is False
        assert result.skip_reason is None

    def test_skipped_result(self) -> None:
        """Test a skipped command result."""
        result = ProfileCommandResult(
            name='ruff',
            command=['ruff', 'check'],
            exit_code=0,
            stdout='',
            stderr='',
            skipped=True,
            skip_reason='ruff not installed',
        )
        assert result.skipped is True
        assert result.skip_reason == 'ruff not installed'


class TestProfileValidationReport:
    """Tests for ProfileValidationReport."""

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        result = ProfileCommandResult(
            name='ruff',
            command=['ruff', 'check'],
            exit_code=0,
            stdout='All good',
            stderr='',
        )
        report = ProfileValidationReport(
            profile='standard', passed=True, results=[result]
        )
        d = report.to_dict()
        assert d['profile'] == 'standard'
        assert d['passed'] is True
        results = d['results']
        assert isinstance(results, list)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, dict)
        assert r['name'] == 'ruff'
        assert 'stdout_excerpt' in r

    def test_to_dict_with_stderr_fallback(self) -> None:
        """Test to_dict uses stderr when stdout is empty."""
        result = ProfileCommandResult(
            name='mypy',
            command=['mypy', '.'],
            exit_code=1,
            stdout='',
            stderr='Found 2 errors',
        )
        report = ProfileValidationReport(
            profile='strict', passed=False, results=[result]
        )
        d = report.to_dict()
        assert d['passed'] is False
        results = d['results']
        assert isinstance(results, list)
        r = results[0]
        assert isinstance(r, dict)
        excerpt = r['stdout_excerpt']
        assert isinstance(excerpt, str)
        assert 'Found 2 errors' in excerpt


class TestToolDetector:
    """Tests for tool detector functions."""

    def test_get_tool_command_ruff(self) -> None:
        """Test ruff command generation."""
        cmd = get_tool_command('ruff', Path('test.py'))
        assert cmd == ['ruff', 'check', 'test.py']

    def test_get_tool_command_mypy(self) -> None:
        """Test mypy command generation."""
        cmd = get_tool_command('mypy', Path('test.py'))
        assert cmd == ['mypy', 'test.py']

    def test_get_tool_command_tsc(self) -> None:
        """Test tsc command generation."""
        cmd = get_tool_command('tsc', Path('test.ts'))
        assert cmd == ['tsc', '--noEmit', 'test.ts']

    def test_get_tool_command_eslint(self) -> None:
        """Test eslint command generation."""
        cmd = get_tool_command('eslint', Path('test.js'))
        assert cmd == ['eslint', 'test.js']

    def test_get_tool_command_unknown(self) -> None:
        """Test unknown tool raises ValueError."""
        with pytest.raises(ValueError, match='Unknown tool'):
            get_tool_command('unknown_tool', Path('test.py'))


class TestParseOutput:
    """Tests for ValidationRunner._parse_output."""

    def test_parse_ruff_output(self) -> None:
        """Test parsing ruff output format."""
        runner = ValidationRunner.__new__(ValidationRunner)
        runner.root = Path()
        stdout = "test.py:2:7: F821 Undefined name 'x'"
        errors, warnings = runner._parse_output('ruff', stdout, '')
        assert len(errors) >= 1
        assert errors[0].error_type == 'ruff'
        assert errors[0].severity == 'error'

    def test_parse_mypy_warning(self) -> None:
        """Test parsing mypy output with warning."""
        runner = ValidationRunner.__new__(ValidationRunner)
        runner.root = Path()
        stdout = 'test.py:10: error: Incompatible types [misc]'
        errors, warnings = runner._parse_output('mypy', stdout, '')
        assert len(errors) >= 1

    def test_parse_skip_non_error_lines(self) -> None:
        """Test parsing skips non-matching lines."""
        runner = ValidationRunner.__new__(ValidationRunner)
        runner.root = Path()
        stdout = 'Success: no issues found'
        errors, warnings = runner._parse_output('mypy', stdout, '')
        assert len(errors) == 0
        assert len(warnings) == 0

    def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        runner = ValidationRunner.__new__(ValidationRunner)
        runner.root = Path()
        errors, warnings = runner._parse_output('ruff', '', '')
        assert len(errors) == 0
        assert len(warnings) == 0
