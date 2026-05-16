"""Tests for auto mode: fully autonomous execution with safety budget."""

from __future__ import annotations

import time
import unittest

from teaagent.auto_mode import (
    AutoModeConfig,
    AutoModeGuard,
    AutoModeLimitError,
)


class TestAutoModeConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        config = AutoModeConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.max_iterations, 50)
        self.assertEqual(config.max_tool_calls, 100)
        self.assertEqual(config.max_cost_cents, 500.0)
        self.assertEqual(config.max_wall_clock_seconds, 600.0)
        self.assertFalse(config.auto_commit)
        self.assertIsNone(config.allowed_tools)
        self.assertIn('workspace_run_shell', config.denied_tools)


class TestAutoModeGuard(unittest.TestCase):
    def test_iteration_limit(self) -> None:
        config = AutoModeConfig(enabled=True, max_iterations=3)
        guard = AutoModeGuard(config=config)
        guard.record_iteration()
        guard.record_iteration()
        with self.assertRaises(AutoModeLimitError) as ctx:
            guard.record_iteration()
        self.assertIn('iteration limit', str(ctx.exception))

    def test_tool_call_limit(self) -> None:
        config = AutoModeConfig(enabled=True, max_tool_calls=2)
        guard = AutoModeGuard(config=config)
        guard.record_tool_call()
        with self.assertRaises(AutoModeLimitError):
            guard.record_tool_call()

    def test_cost_limit(self) -> None:
        config = AutoModeConfig(enabled=True, max_cost_cents=100.0)
        guard = AutoModeGuard(config=config)
        guard.record_cost(60.0)
        with self.assertRaises(AutoModeLimitError):
            guard.record_cost(50.0)

    def test_wall_clock_limit(self) -> None:
        config = AutoModeConfig(
            enabled=True, max_wall_clock_seconds=0.1, max_iterations=1000
        )
        guard = AutoModeGuard(config=config)
        time.sleep(0.15)
        with self.assertRaises(AutoModeLimitError):
            guard.record_iteration()

    def test_tool_allowed_with_whitelist(self) -> None:
        config = AutoModeConfig(
            enabled=True,
            allowed_tools=frozenset({'workspace_read_file', 'workspace_write_file'}),
        )
        guard = AutoModeGuard(config=config)
        self.assertTrue(guard.is_tool_allowed('workspace_read_file'))
        self.assertFalse(guard.is_tool_allowed('workspace_run_shell'))

    def test_tool_allowed_with_denylist(self) -> None:
        config = AutoModeConfig(
            enabled=True,
            denied_tools=frozenset({'dangerous_tool'}),
        )
        guard = AutoModeGuard(config=config)
        self.assertTrue(guard.is_tool_allowed('safe_tool'))
        self.assertFalse(guard.is_tool_allowed('dangerous_tool'))

    def test_summary(self) -> None:
        config = AutoModeConfig(enabled=True)
        guard = AutoModeGuard(config=config)
        guard.record_iteration()
        guard.record_tool_call()
        guard.record_cost(10.0)
        summary = guard.summary()
        self.assertTrue(summary['auto_mode'])
        self.assertEqual(summary['iterations'], 1)
        self.assertEqual(summary['tool_calls'], 1)
        self.assertEqual(summary['cost_cents'], 10.0)


if __name__ == '__main__':
    unittest.main()
