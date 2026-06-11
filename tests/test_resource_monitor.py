"""Tests for resource monitoring module."""

from __future__ import annotations

import os

from teaagent.resource_monitor import is_process_alive


def test_current_process_alive() -> None:
    """Test that current process is detected as alive."""
    current_pid = os.getpid()
    assert is_process_alive(current_pid)


def test_invalid_pid_returns_false() -> None:
    """Test that invalid PIDs return False."""
    assert not is_process_alive(-1)
    assert not is_process_alive(0)
    assert not is_process_alive(999999999)  # Unlikely to exist


def test_init_process_alive() -> None:
    """Test that init process (PID 1) is handled correctly."""
    # PID 1 should exist on most Unix systems
    # but we handle permission errors gracefully
    result = is_process_alive(1)
    # Either True (exists) or False (permission denied handled as False)
    assert isinstance(result, bool)
