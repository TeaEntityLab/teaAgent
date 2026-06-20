"""G-P2-3: BudgetMonitor iteration and tool-call warning tests.

Ensures that iteration and tool-call consumption emit warnings at the same
50/80/90/100 % threshold levels as the existing cost monitoring.
"""

from __future__ import annotations

import logging

from teaagent.budget_monitor import BudgetAction, BudgetMonitor
from teaagent.types import RunBudget


def test_iteration_warning_at_50_percent(caplog) -> None:
    caplog.set_level(logging.WARNING, logger='teaagent.budget_monitor')
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=False,
    )
    action = monitor.check_iterations(run_id='iter-50', iterations=5)
    assert action == BudgetAction.WARN
    assert any('iterations' in r.message and '50%' in r.message for r in caplog.records)


def test_iteration_warning_at_80_percent(caplog) -> None:
    caplog.set_level(logging.WARNING, logger='teaagent.budget_monitor')
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=False,
    )
    action = monitor.check_iterations(run_id='iter-80', iterations=8)
    assert action == BudgetAction.WARN
    assert any('80%' in r.message for r in caplog.records)


def test_iteration_100_percent_suggests_read_only() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=True,
    )
    action = monitor.check_iterations(run_id='iter-100', iterations=10)
    assert action == BudgetAction.SUGGEST_READ_ONLY


def test_iteration_90_percent_non_interactive_warns() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=False,
    )
    action = monitor.check_iterations(run_id='iter-90', iterations=9)
    assert action == BudgetAction.WARN


def test_iteration_90_percent_interactive_prompt_can_cancel() -> None:
    prompted: list[dict] = []

    def handler(payload: dict) -> bool:
        prompted.append(payload)
        return False

    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=True,
        on_prompt=handler,
    )
    action = monitor.check_iterations(run_id='iter-90-cancel', iterations=9)
    assert action == BudgetAction.PROMPT_CONFIRM
    assert prompted
    assert prompted[0]['dimension'] == 'iterations'


def test_iteration_warnings_idempotent() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        interactive=False,
    )
    action1 = monitor.check_iterations(run_id='iter-idem', iterations=5)
    assert action1 == BudgetAction.WARN
    action2 = monitor.check_iterations(run_id='iter-idem', iterations=5)
    assert action2 == BudgetAction.NONE


def test_tool_call_warning_at_50_percent(caplog) -> None:
    caplog.set_level(logging.WARNING, logger='teaagent.budget_monitor')
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=10),
        interactive=False,
    )
    action = monitor.check_tool_calls(run_id='tc-50', tool_calls=5)
    assert action == BudgetAction.WARN
    assert any('tool_calls' in r.message and '50%' in r.message for r in caplog.records)


def test_tool_call_100_percent_suggests_read_only() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=10),
        interactive=True,
    )
    action = monitor.check_tool_calls(run_id='tc-100', tool_calls=10)
    assert action == BudgetAction.SUGGEST_READ_ONLY


def test_tool_call_warnings_idempotent() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=10),
        interactive=False,
    )
    action1 = monitor.check_tool_calls(run_id='tc-idem', tool_calls=5)
    assert action1 == BudgetAction.WARN
    action2 = monitor.check_tool_calls(run_id='tc-idem', tool_calls=5)
    assert action2 == BudgetAction.NONE


def test_iteration_and_cost_dimensions_independent() -> None:
    """Iteration and cost emitted-level sets are tracked independently."""
    monitor = BudgetMonitor(
        budget=RunBudget(
            max_iterations=10, max_tool_calls=0, max_estimated_cost_cents=100
        ),
        interactive=False,
    )
    # Burn through cost thresholds first.
    cost_action = monitor.check(run_id='combo', cost_cents=100.0)
    assert cost_action == BudgetAction.SUGGEST_READ_ONLY
    # Iteration warnings should still fire independently.
    iter_action = monitor.check_iterations(run_id='combo', iterations=5)
    assert iter_action == BudgetAction.WARN


def test_iteration_tui_status_callback() -> None:
    statuses: list[str] = []
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=0),
        on_status=statuses.append,
        interactive=False,
    )
    monitor.check_iterations(run_id='iter-status', iterations=5)
    assert len(statuses) == 1
    assert 'iterations' in statuses[0]
    assert '50%' in statuses[0]


def test_tool_call_tui_status_callback() -> None:
    statuses: list[str] = []
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=10),
        on_status=statuses.append,
        interactive=False,
    )
    # 8/10 = 80 %, which crosses both the 50 % and 80 % thresholds in one call.
    monitor.check_tool_calls(run_id='tc-status', tool_calls=8)
    assert len(statuses) == 2
    assert all('tool_calls' in s for s in statuses)
    assert any('80%' in s for s in statuses)


def test_reset_clears_iteration_and_tool_call_levels() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=10, max_tool_calls=10),
        interactive=False,
    )
    monitor.check_iterations(run_id='reset-iter', iterations=5)
    monitor.check_tool_calls(run_id='reset-tc', tool_calls=5)
    assert monitor._emitted_iteration_levels == {50}
    assert monitor._emitted_tool_call_levels == {50}
    monitor.reset()
    assert monitor._emitted_iteration_levels == set()
    assert monitor._emitted_tool_call_levels == set()
    # After reset, warnings fire again.
    assert (
        monitor.check_iterations(run_id='reset-iter-2', iterations=5)
        == BudgetAction.WARN
    )
    assert (
        monitor.check_tool_calls(run_id='reset-tc-2', tool_calls=5) == BudgetAction.WARN
    )


def test_zero_max_iterations_returns_none() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=0),
    )
    assert (
        monitor.check_iterations(run_id='zero-iter', iterations=5) == BudgetAction.NONE
    )


def test_zero_max_tool_calls_returns_none() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_iterations=0, max_tool_calls=0),
    )
    assert monitor.check_tool_calls(run_id='zero-tc', tool_calls=5) == BudgetAction.NONE
