"""Tests for WASM runtime."""

import tempfile
from pathlib import Path

from teaagent.wasm_runtime import (
    WASMExecutionResult,
    WASMRuntime,
    is_wasm_available,
)

try:
    from teaagent.wasm_runtime import WASMER_AVAILABLE
except ImportError:
    WASMER_AVAILABLE = False


def test_is_wasm_available():
    """Test checking WASM availability."""
    available = is_wasm_available()
    # This will be False unless wasmer is installed
    assert isinstance(available, bool)


def test_wasm_runtime_init_without_wasmer():
    """Test that WASM runtime raises ImportError without wasmer."""
    if is_wasm_available():
        # Skip test if wasmer is available
        return

    try:
        WASMRuntime(memory_limit_mb=128)
        raise AssertionError('Should have raised ImportError')
    except ImportError as exc:
        assert 'wasmer' in str(exc).lower()


def test_wasm_runtime_check_compatibility():
    """Test checking skill compatibility with WASM."""
    if not is_wasm_available():
        # Skip test if wasmer is not available
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)

        # Create a simple Python file
        (skill_path / 'skill.py').write_text(
            'def run():\n    return "hello"\n',
            encoding='utf-8',
        )

        runtime = WASMRuntime(memory_limit_mb=128)
        result = runtime.check_compatibility(skill_path)

        assert 'compatible' in result
        assert 'issues' in result
        assert 'warnings' in result


def test_wasm_runtime_check_compatibility_async():
    """Test that async/await is detected as incompatible."""
    if not is_wasm_available():
        # Skip test if wasmer is not available
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)

        # Create a Python file with async/await
        (skill_path / 'skill.py').write_text(
            'async def run():\n    return "hello"\n',
            encoding='utf-8',
        )

        runtime = WASMRuntime(memory_limit_mb=128)
        result = runtime.check_compatibility(skill_path)

        assert result['compatible'] is False
        assert any('async/await' in issue for issue in result['issues'])


def test_wasm_runtime_check_compatibility_socket():
    """Test that socket module usage is warned."""
    if not is_wasm_available():
        # Skip test if wasmer is not available
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)

        # Create a Python file with socket import
        (skill_path / 'skill.py').write_text(
            'import socket\n\ndef run():\n    return "hello"\n',
            encoding='utf-8',
        )

        runtime = WASMRuntime(memory_limit_mb=128)
        result = runtime.check_compatibility(skill_path)

        assert 'compatible' in result
        assert any('socket' in warning for warning in result['warnings'])


def test_wasm_execution_result_creation():
    """Test creating WASM execution result."""
    result = WASMExecutionResult(
        success=True,
        output='test output',
        execution_time_ms=100.0,
        memory_used_mb=50.0,
    )

    assert result.success is True
    assert result.output == 'test output'
    assert result.execution_time_ms == 100.0
    assert result.memory_used_mb == 50.0


def test_wasm_execution_result_with_error():
    """Test creating WASM execution result with error."""
    result = WASMExecutionResult(
        success=False,
        output='',
        error='Execution failed',
        execution_time_ms=50.0,
    )

    assert result.success is False
    assert result.error == 'Execution failed'
