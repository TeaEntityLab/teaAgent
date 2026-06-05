from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from teaagent.budget import RunBudget
from teaagent.errors import BudgetExceededError


class RunBudgetTests(unittest.TestCase):
    def test_default_values_are_valid(self) -> None:
        budget = RunBudget()
        budget.validate()

    def test_zero_iterations_raises(self) -> None:
        budget = RunBudget(max_iterations=0)
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_iterations', str(ctx.exception))

    def test_negative_iterations_raises(self) -> None:
        budget = RunBudget(max_iterations=-1)
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_iterations', str(ctx.exception))

    def test_negative_tool_calls_raises(self) -> None:
        budget = RunBudget(max_tool_calls=-1)
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('max_tool_calls', str(ctx.exception))

    def test_zero_tool_calls_is_valid(self) -> None:
        budget = RunBudget(max_tool_calls=0)
        budget.validate()

    def test_negative_cost_raises(self) -> None:
        budget = RunBudget(max_estimated_cost_cents=-1)
        with self.assertRaises(ValueError) as ctx:
            budget.validate()
        self.assertIn('cost_cents', str(ctx.exception))

    def test_none_cost_budget_skips_preflight(self) -> None:
        budget = RunBudget(max_estimated_cost_cents=None)
        with patch('teaagent.budget.estimate_cost_preflight') as mock_estimate:
            budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)
        mock_estimate.assert_not_called()

    def test_zero_cost_budget_blocks_preflight(self) -> None:
        """0 means zero spend allowed - any positive cost exceeds it."""
        budget = RunBudget(max_estimated_cost_cents=0)
        with (
            patch('teaagent.budget.estimate_cost_preflight', return_value=1),
            self.assertRaises(BudgetExceededError),
        ):
            budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)

    def test_zero_cost_budget_allows_zero_cost(self) -> None:
        """0 cap allows exactly zero cost."""
        budget = RunBudget(max_estimated_cost_cents=0)
        with patch('teaagent.budget.estimate_cost_preflight', return_value=0):
            result = budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)
        self.assertIsNone(result)

    def test_budget_is_frozen(self) -> None:
        budget = RunBudget()
        with self.assertRaises(FrozenInstanceError):
            budget.max_iterations = 99  # type: ignore[misc]

    def test_custom_valid_budget(self) -> None:
        budget = RunBudget(
            max_iterations=5, max_tool_calls=3, max_estimated_cost_cents=50
        )
        budget.validate()


if __name__ == '__main__':
    unittest.main()
