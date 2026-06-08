from __future__ import annotations

import logging

from teaagent.budget_monitor import BudgetAction, BudgetMonitor
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.types import AuditLogger, RunBudget, ToolRegistry


def test_budget_warning_events_emitted_at_thresholds() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
        ),
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 95.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-budget-warn')
    assert result.status == 'completed'
    levels = [
        e.payload.get('level')
        for e in audit.events
        if getattr(e, 'event_type', None) == 'budget_warning'
    ]
    assert levels == [50, 80, 90]


def test_budget_prompt_handler_can_cancel_run() -> None:
    audit = AuditLogger()
    prompted: list[dict] = []

    def handler(payload: dict) -> bool:
        prompted.append(payload)
        return False

    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
        ),
        budget_prompt_handler=handler,
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 90.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-budget-cancel')
    assert result.status.startswith('failed:')
    assert prompted
    assert any(getattr(e, 'event_type', None) == 'budget_prompt' for e in audit.events)


def test_budget_prompt_handler_can_continue_run() -> None:
    audit = AuditLogger()

    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
        ),
        budget_prompt_handler=lambda _payload: True,
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 90.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-budget-continue')
    assert result.status == 'completed'


def test_budget_warning_100_percent_read_only_suggestion() -> None:
    audit = AuditLogger()
    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=100
        ),
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 100.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-budget-100')
    assert result.status == 'completed'
    levels = [
        e.payload.get('level')
        for e in audit.events
        if getattr(e, 'event_type', None) == 'budget_warning'
    ]
    assert 100 in levels
    read_only_events = [
        e
        for e in audit.events
        if getattr(e, 'event_type', None) == 'budget_read_only_suggested'
    ]
    assert len(read_only_events) == 1
    assert read_only_events[0].payload['percent'] == 100.0


def test_budget_monitor_logs_warnings(caplog) -> None:
    caplog.set_level(logging.WARNING, logger='teaagent.budget_monitor')
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
        interactive=False,
    )
    monitor.check(run_id='test-log', cost_cents=50.0)
    monitor.check(run_id='test-log', cost_cents=80.0)
    monitor.check(run_id='test-log', cost_cents=90.0)
    monitor.check(run_id='test-log', cost_cents=100.0)

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) >= 4
    assert any('50%' in msg for msg in warnings)
    assert any('80%' in msg for msg in warnings)
    assert any('90%' in msg for msg in warnings)
    assert any('100%' in msg or 'exhausted' in msg for msg in warnings)


def test_budget_monitor_non_interactive_no_prompt(caplog) -> None:
    caplog.set_level(logging.WARNING, logger='teaagent.budget_monitor')
    prompted: list[dict] = []

    def handler(payload: dict) -> bool:
        prompted.append(payload)
        return False

    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
        interactive=False,
        on_prompt=handler,
    )
    action = monitor.check(run_id='test-ni', cost_cents=90.0)
    assert action == BudgetAction.WARN
    assert len(prompted) == 0

    all_messages = ' '.join(r.message for r in caplog.records)
    assert 'auto-continuing' in all_messages or 'non-interactive' in all_messages


def test_budget_monitor_100_percent_suggests_read_only() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
        interactive=True,
    )
    action = monitor.check(run_id='test-100', cost_cents=100.0)
    assert action == BudgetAction.SUGGEST_READ_ONLY


def test_budget_monitor_idempotent() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
    )
    action1 = monitor.check(run_id='test-idem', cost_cents=50.0)
    assert action1 == BudgetAction.WARN
    action2 = monitor.check(run_id='test-idem', cost_cents=50.0)
    assert action2 == BudgetAction.NONE


def test_budget_monitor_tui_status_callback() -> None:
    statuses: list[str] = []
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
        on_status=statuses.append,
        interactive=False,
    )
    monitor.check(run_id='test-tui', cost_cents=50.0)
    assert len(statuses) == 1
    assert '50%' in statuses[0]


def test_budget_monitor_reset() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=100),
        interactive=False,
    )
    monitor.check(run_id='test-r1', cost_cents=50.0)
    assert monitor._emitted_levels == {50}
    monitor.reset()
    assert monitor._emitted_levels == set()
    action = monitor.check(run_id='test-r2', cost_cents=50.0)
    assert action == BudgetAction.WARN


def test_budget_monitor_zero_budget_returns_none() -> None:
    """0 cap is enforced by runner; monitor returns NONE."""
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=0),
    )
    action = monitor.check(run_id='test-zero', cost_cents=0)
    assert action == BudgetAction.NONE


def test_budget_monitor_none_budget_returns_none() -> None:
    monitor = BudgetMonitor(
        budget=RunBudget(max_estimated_cost_cents=None),
    )
    action = monitor.check(run_id='test-none', cost_cents=50.0)
    assert action == BudgetAction.NONE


def test_budget_zero_cents_rejects_any_spend() -> None:
    """0 cap: any positive cost fails immediately at the runner level."""
    audit = AuditLogger()
    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=0
        ),
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 1.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-zero-cap')
    assert result.status.startswith('failed:')
    assert result.error_message is not None
    assert 'budget' in result.error_message.lower()


def test_budget_none_allows_unlimited() -> None:
    """None cap: arbitrarily large cost is allowed — run completes normally."""
    audit = AuditLogger()
    runner = AgentRunner(
        registry=ToolRegistry(),
        audit=audit,
        budget=RunBudget(
            max_iterations=3, max_tool_calls=0, max_estimated_cost_cents=None
        ),
    )

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 999_999.0
        return FinalAnswer('ok')

    result = runner.run(task='t', decide=decide, run_id='run-none-cap')
    assert result.status == 'completed'


def test_budget_default_500_cents() -> None:
    """RunBudget() default cap is exactly 500 cents."""
    assert RunBudget().max_estimated_cost_cents == 500
