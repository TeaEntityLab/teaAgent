"""Acceptance tests for Pre-flight Environment Health Checks."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from teaagent.preflight import check_env_health


class TestPreflightEnvHealth(unittest.TestCase):
    def test_health_check_passes_on_normal_dir(self) -> None:
        with TemporaryDirectory() as td:
            report = check_env_health(Path(td))
            self.assertTrue(report['healthy'])
            self.assertEqual(len(report['failures']), 0)

    def test_health_check_detects_readonly_dir(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            # Create a subdir and make it read-only
            sub = root / 'readonly_part'
            sub.mkdir()
            sub.chmod(0o444)

            try:
                # We want check_env_health to detect this if it's a critical path like .teaagent
                report = check_env_health(root, critical_paths=[sub])
                self.assertFalse(report['healthy'])
                self.assertTrue(
                    any('Permission denied' in f for f in report['failures'])
                )
            finally:
                sub.chmod(0o777)  # Clean up

    @patch('socket.socket.bind')
    def test_health_check_detects_network_restriction(self, mock_bind) -> None:
        from socket import error as socket_error

        mock_bind.side_effect = socket_error('Permission denied')

        report = check_env_health(Path('.'))
        # If we check for port binding ability
        self.assertTrue(any('Network binding' in f for f in report['failures']))


if __name__ == '__main__':
    unittest.main()
