"""Tests for sandbox CLI handlers."""

import argparse
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from teaagent.cli._handlers._sandbox import (
    sandbox_check_compatibility_command,
    sandbox_check_wasm_command,
    sandbox_monitor_command,
    sandbox_route_command,
)
from teaagent.wasm_runtime import is_wasm_available


def test_sandbox_route_command():
    """Test routing a skill to a sandbox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        args = argparse.Namespace(
            skill_path=str(skill_path),
            risk_level='low',
            preferred_sandbox=None,
            default_sandbox='auto',
            wasm_memory_limit_mb=256,
            docker_cpu_quota=None,
            docker_memory_limit=None,
            show_config=False,
        )

        result = sandbox_route_command(args)
        assert result == 0


def test_sandbox_route_command_with_config():
    """Test routing a skill and showing configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        args = argparse.Namespace(
            skill_path=str(skill_path),
            risk_level='medium',
            preferred_sandbox='docker',
            default_sandbox='auto',
            wasm_memory_limit_mb=256,
            docker_cpu_quota=2.0,
            docker_memory_limit='1g',
            show_config=True,
        )

        result = sandbox_route_command(args)
        assert result == 0


def test_sandbox_route_command_invalid_path():
    """Test routing with invalid skill path."""
    args = argparse.Namespace(
        skill_path='/nonexistent/path',
        risk_level='low',
        preferred_sandbox=None,
        default_sandbox='auto',
        wasm_memory_limit_mb=256,
        docker_cpu_quota=None,
        docker_memory_limit=None,
        show_config=False,
    )

    result = sandbox_route_command(args)
    assert result == 1


def test_sandbox_check_wasm_command():
    """Test checking WASM availability."""
    args = argparse.Namespace()
    result = sandbox_check_wasm_command(args)

    # Should return 0 if available, 1 if not
    assert result in (0, 1)


def test_sandbox_check_compatibility_command():
    """Test checking skill compatibility."""
    if not is_wasm_available():
        # Skip test if WASM is not available
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_path = Path(tmpdir)
        (skill_path / 'skill.py').write_text(
            'def run(): return "hello"', encoding='utf-8'
        )

        args = argparse.Namespace(
            skill_path=str(skill_path),
            memory_limit_mb=256,
        )

        result = sandbox_check_compatibility_command(args)
        assert result == 0


def test_sandbox_check_compatibility_command_invalid_path():
    """Test checking compatibility with invalid path."""
    args = argparse.Namespace(
        skill_path='/nonexistent/path',
        memory_limit_mb=256,
    )

    result = sandbox_check_compatibility_command(args)
    assert result == 1


def test_sandbox_monitor_command():
    """Test monitoring a container."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='50.0%,512MiB / 1GiB',
            stderr='',
        )

        args = argparse.Namespace(
            container_id='test-container',
            cpu_limit_cores=2.0,
            memory_limit_mb=1024,
            duration=None,
            check_interval=5.0,
        )

        result = sandbox_monitor_command(args)
        assert result == 0


def test_sandbox_monitor_command_with_duration():
    """Test monitoring a container for a duration."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='50.0%,512MiB / 1GiB',
            stderr='',
        )

        args = argparse.Namespace(
            container_id='test-container',
            cpu_limit_cores=2.0,
            memory_limit_mb=1024,
            duration=0.1,
            check_interval=0.05,
        )

        result = sandbox_monitor_command(args)
        assert result == 0
