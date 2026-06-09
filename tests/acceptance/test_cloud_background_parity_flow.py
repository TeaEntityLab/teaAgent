"""Acceptance: local background runs preserve CLI permission/audit contract."""

from __future__ import annotations

import argparse

from teaagent.ergonomics.background_run import build_agent_run_command
from teaagent.integration.run_state import (
    RUN_STATE_SCHEMA_VERSION,
    build_attach_snapshot,
)
from teaagent.run_store import RunResult, RunStore


def test_background_command_argv_matches_foreground_governance_flags(tmp_path) -> None:
    args = argparse.Namespace(
        provider='gpt',
        model='gpt-4o-mini',
        root=str(tmp_path),
        route_model=False,
        max_iterations=10,
        max_tool_calls=10,
        clarify=False,
        allow_destructive=False,
        approve_call_id=[],
        hitl_approval=False,
        permission_mode='read-only',
        subagent=False,
        max_subagent_depth=1,
        heartbeat=0.0,
        code_analysis=False,
    )
    cmd = build_agent_run_command(args, 'parity smoke')
    assert 'parity smoke' in cmd
    assert '--permission-mode' in cmd
    assert 'read-only' in cmd
    assert '--root' in cmd and str(tmp_path) in cmd


def test_background_and_foreground_runs_share_attach_snapshot_schema(tmp_path) -> None:
    store = RunStore(tmp_path)
    for run_id, mode in (
        ('run-fg', 'prompt'),
        ('run-bg', 'read-only'),
    ):
        audit = store.audit_logger(run_id)
        audit.record(
            'run_started',
            run_id,
            task='parity',
            permission_mode=mode,
        )
        audit.record('run_completed', run_id, answer='done', cost_cents=12)
        store.logger_for_result(
            RunResult(
                run_id=run_id,
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='completed',
                cost_cents=12,
            ),
            audit,
        )

    fg = build_attach_snapshot(store, 'run-fg')
    bg = build_attach_snapshot(store, 'run-bg')
    for key in ('run_state', 'pending_approval', 'event_count', 'run_id'):
        assert key in fg
        assert key in bg
    assert fg['run_state']['schema_version'] == RUN_STATE_SCHEMA_VERSION
    assert bg['run_state']['schema_version'] == RUN_STATE_SCHEMA_VERSION
    assert fg['run_state']['permission_mode'] == 'prompt'
    assert bg['run_state']['permission_mode'] == 'read-only'
    assert fg['run_state']['cost_cents'] == bg['run_state']['cost_cents'] == 12.0
