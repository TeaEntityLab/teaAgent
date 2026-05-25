"""Automation background argv must match foreground agent run for the same spec."""

from __future__ import annotations

import argparse

from teaagent.automations import AutomationStore
from teaagent.cli._handlers._agent import _start_automation_background_run
from teaagent.ergonomics.background_run import build_agent_run_command


def test_automation_and_manual_run_share_tool_context_flags(tmp_path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.draft(
        name='parity',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider='gpt',
        model='default',
        permission_mode='workspace-write',
        context_profile='balanced',
        max_iterations=5,
        max_tool_calls=6,
        delivery='background_log',
        selected_skills=['alpha'],
        requires_subagent=True,
        max_cost_cents=50,
    )
    manual = argparse.Namespace(
        root=str(tmp_path),
        provider=spec.provider,
        model=spec.model,
        route_model=False,
        max_iterations=spec.max_iterations,
        max_tool_calls=spec.max_tool_calls,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode=spec.permission_mode,
        subagent=True,
        heartbeat=0.0,
        code_analysis=False,
        context_profile=spec.context_profile,
        selected_skills=list(spec.selected_skills),
        max_estimated_cost_cents=spec.max_cost_cents,
    )
    manual_cmd = build_agent_run_command(manual, spec.task)
    auto_record = _start_automation_background_run(
        root=str(tmp_path), spec=spec, task=spec.task
    )
    auto_cmd = auto_record['command']
    for flag in (
        '--permission-mode',
        'workspace-write',
        '--context-profile',
        'balanced',
        '--skill',
        'alpha',
        '--subagent',
        '--max-estimated-cost-cents',
        '50',
    ):
        assert flag in manual_cmd
        assert flag in auto_cmd
    assert manual_cmd == auto_cmd
