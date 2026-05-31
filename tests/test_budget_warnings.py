from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.tools import ToolRegistry


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
