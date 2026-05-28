"""Tests for automatic context compaction features."""

from __future__ import annotations

import unittest

from teaagent.context import CompactionManager, ContextCompactor


class AutoCompactionTests(unittest.TestCase):
    def test_compaction_manager_auto_trigger(self) -> None:
        """Test that compaction manager triggers automatically."""
        compactor = ContextCompactor(
            recent_observations=2,
            threshold_low=0.5,
            threshold_high=0.8,
        )
        manager = CompactionManager(
            compactor=compactor,
            auto_compact_enabled=True,
            check_interval=1,
            max_context_tokens=100,
        )

        # Create context that exceeds threshold
        context = {
            'observations': [
                {'tool_name': f'tool_{i}', 'result': {'data': 'x' * 50}}
                for i in range(10)
            ]
        }

        # First check should trigger compaction
        result = manager.check_and_compact(context)
        self.assertIsNotNone(result)
        self.assertLess(
            len(result.context['observations']), len(context['observations'])
        )

    def test_compaction_manager_respects_interval(self) -> None:
        """Test that compaction manager respects check interval."""
        compactor = ContextCompactor(threshold_low=0.5, threshold_high=0.8)
        manager = CompactionManager(
            compactor=compactor,
            auto_compact_enabled=True,
            check_interval=5,  # Only check every 5 operations
            max_context_tokens=100,
        )

        context = {
            'observations': [
                {'tool_name': f'tool_{i}', 'result': {'data': 'x' * 50}}
                for i in range(10)
            ]
        }

        # First 4 checks should not trigger
        for _ in range(4):
            result = manager.check_and_compact(context)
            self.assertIsNone(result)

        # 5th check should trigger
        result = manager.check_and_compact(context)
        self.assertIsNotNone(result)

    def test_compaction_manager_disabled(self) -> None:
        """Test that compaction can be disabled."""
        compactor = ContextCompactor(threshold_low=0.5, threshold_high=0.8)
        manager = CompactionManager(
            compactor=compactor,
            auto_compact_enabled=False,  # Disabled
            max_context_tokens=100,
        )

        context = {
            'observations': [
                {'tool_name': f'tool_{i}', 'result': {'data': 'x' * 50}}
                for i in range(10)
            ]
        }

        # Should never trigger when disabled
        for _ in range(10):
            result = manager.check_and_compact(context)
            self.assertIsNone(result)

    def test_compaction_manager_token_estimation(self) -> None:
        """Test that compaction manager can estimate tokens when not provided."""
        compactor = ContextCompactor(threshold_low=0.5, threshold_high=0.8)
        manager = CompactionManager(
            compactor=compactor,
            auto_compact_enabled=True,
            check_interval=1,
            max_context_tokens=100,
        )

        context = {
            'observations': [
                {'tool_name': f'tool_{i}', 'result': {'data': 'x' * 50}}
                for i in range(10)
            ]
        }

        # Should estimate tokens automatically
        result = manager.check_and_compact(context, current_tokens=None)
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
