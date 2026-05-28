"""Integration tests for LSP self-healing validation features."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.validation import (
    ValidationResult,
    ValidationRunner,
    detect_available_tools,
)
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
    def temp_root(self) -> Path:
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

        runner = ValidationRunner(root=temp_root, timeout=0.1)

        with patch('shutil.which') as mock_which:
            mock_which.return_value = '/usr/bin/ruff'

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
