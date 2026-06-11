"""Acceptance tests for Pre-flight Environment Health Checks."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from teaagent.preflight import check_env_health
from test_support import can_bind_loopback


def test_health_check_passes_on_normal_dir() -> None:
    with TemporaryDirectory() as td:
        report = check_env_health(Path(td))
        if not can_bind_loopback():
            assert not report['healthy']
            assert any('Network binding' in f for f in report['failures'])
            return

        assert report['healthy']
        assert len(report['failures']) == 0


def test_health_check_detects_readonly_dir() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        # Create a subdir and make it read-only
        sub = root / 'readonly_part'
        sub.mkdir()
        sub.chmod(0o444)

        try:
            # We want check_env_health to detect this if it's a critical path like .teaagent
            report = check_env_health(root, critical_paths=[sub])
            assert not report['healthy']
            assert any('Permission denied' in f for f in report['failures'])
        finally:
            sub.chmod(0o777)  # Clean up


@patch('socket.socket.bind')
def test_health_check_detects_network_restriction(mock_bind) -> None:
    from socket import error as socket_error

    mock_bind.side_effect = socket_error('Permission denied')

    report = check_env_health(Path('.'))
    # If we check for port binding ability
    assert any('Network binding' in f for f in report['failures'])
