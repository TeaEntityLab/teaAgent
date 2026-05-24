from __future__ import annotations

from teaagent.automations import AutomationSpec
from teaagent.chat_agent import ChatAgentConfig
from teaagent.ergonomics.background_run import build_agent_run_command


def test_automation_background_command_includes_cost_cap() -> None:
    spec = AutomationSpec(
        automation_id='a1',
        name='cap',
        task='check repo status and write summary to notes.txt',
        schedule='every 30m',
        max_cost_cents=42,
    )
    import argparse

    args = argparse.Namespace(
        root='.',
        provider=None,
        model=None,
        route_model=False,
        max_iterations=5,
        max_tool_calls=5,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode='read-only',
        subagent=False,
        heartbeat=0.0,
        code_analysis=False,
        context_profile='lean',
        selected_skills=[],
        max_estimated_cost_cents=spec.max_cost_cents,
    )
    cmd = build_agent_run_command(args, spec.task)
    assert '--max-estimated-cost-cents' in cmd
    assert '42' in cmd


def test_chat_agent_config_cost_cap_defaults_to_runner_budget() -> None:
    config = ChatAgentConfig.from_root('.', max_estimated_cost_cents=25)
    assert config.max_estimated_cost_cents == 25
