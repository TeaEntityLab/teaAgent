# test-type: behavior
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
    # PID 1 (init/launchd) always exists on Unix. os.kill(1, 0) either
    # succeeds (→ True) or raises EPERM which is handled as True (process
    # exists but we lack permission). Either way the process is alive.
    result = is_process_alive(1)
    assert result is True
