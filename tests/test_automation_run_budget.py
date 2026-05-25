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


def test_background_command_preserves_run_surface_flags() -> None:
    import argparse

    args = argparse.Namespace(
        root='.',
        provider='gpt',
        model='gpt-test',
        route_model=True,
        max_iterations=4,
        max_tool_calls=5,
        clarify=True,
        allow_destructive=False,
        approve_call_id=['call-1'],
        hitl_approval=True,
        permission_mode='workspace-write',
        subagent=True,
        max_subagent_depth=2,
        heartbeat=1.5,
        code_analysis=True,
        telemetry_otlp_endpoint='http://127.0.0.1:4318/v1/traces',
        telemetry_service_name='teaagent-bg',
        telemetry_console=True,
        checkpoint_store='checkpoints.sqlite3',
        progress=True,
        no_progress=False,
        stream=True,
        stream_raw=True,
        json_stream=True,
        context_profile='deep',
        selected_skills=['alpha'],
        skill_index_only=True,
        max_estimated_cost_cents=7,
    )
    cmd = build_agent_run_command(args, 'summarize')
    for flag in (
        '--route-model',
        '--clarify',
        '--approve-call-id',
        'call-1',
        '--hitl-approval',
        '--permission-mode',
        'workspace-write',
        '--subagent',
        '--max-subagent-depth',
        '2',
        '--heartbeat',
        '1.5',
        '--code-analysis',
        '--telemetry-otlp-endpoint',
        'http://127.0.0.1:4318/v1/traces',
        '--telemetry-service-name',
        'teaagent-bg',
        '--telemetry-console',
        '--checkpoint-store',
        'checkpoints.sqlite3',
        '--progress',
        '--stream',
        '--stream-raw',
        '--json-stream',
        '--context-profile',
        'deep',
        '--skill-index-only',
        '--skill',
        'alpha',
        '--max-estimated-cost-cents',
        '7',
    ):
        assert flag in cmd


def test_chat_agent_config_cost_cap_defaults_to_runner_budget() -> None:
    config = ChatAgentConfig.from_root('.', max_estimated_cost_cents=25)
    assert config.max_estimated_cost_cents == 25
