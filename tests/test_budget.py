from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from teaagent.types import BudgetExceededError, RunBudget


def test_default_values_are_valid() -> None:
    budget = RunBudget()
    budget.validate()


def test_zero_iterations_raises() -> None:
    budget = RunBudget(max_iterations=0)
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_iterations' in str(ctx.value)


def test_negative_iterations_raises() -> None:
    budget = RunBudget(max_iterations=-1)
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_iterations' in str(ctx.value)


def test_negative_tool_calls_raises() -> None:
    budget = RunBudget(max_tool_calls=-1)
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'max_tool_calls' in str(ctx.value)


def test_zero_tool_calls_is_valid() -> None:
    budget = RunBudget(max_tool_calls=0)
    budget.validate()


def test_negative_cost_raises() -> None:
    budget = RunBudget(max_estimated_cost_cents=-1)
    with pytest.raises(ValueError) as ctx:
        budget.validate()
    assert 'cost_cents' in str(ctx.value)


def test_none_cost_budget_skips_preflight() -> None:
    budget = RunBudget(max_estimated_cost_cents=None)
    with patch('teaagent.budget.estimate_cost_preflight') as mock_estimate:
        budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)
    mock_estimate.assert_not_called()


def test_zero_cost_budget_blocks_preflight() -> None:
    """0 means zero spend allowed - any positive cost exceeds it."""
    budget = RunBudget(max_estimated_cost_cents=0)
    with (
        patch('teaagent.budget.estimate_cost_preflight', return_value=1),
        pytest.raises(BudgetExceededError),
    ):
        budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)


def test_zero_cost_budget_allows_zero_cost() -> None:
    """0 cap allows exactly zero cost."""
    budget = RunBudget(max_estimated_cost_cents=0)
    with patch('teaagent.budget.estimate_cost_preflight', return_value=0):
        result = budget.check_cost_preflight('gpt', 'gpt-4o-mini', 100, 10)
    assert result is None


def test_budget_is_frozen() -> None:
    budget = RunBudget()
    with pytest.raises(FrozenInstanceError):
        budget.max_iterations = 99


def test_custom_valid_budget() -> None:
    budget = RunBudget(max_iterations=5, max_tool_calls=3, max_estimated_cost_cents=50)
    budget.validate()
