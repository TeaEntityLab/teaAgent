"""SURF-001: shared run-state schema across surfaces."""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.run_state import (
    RUN_STATE_SCHEMA_VERSION,
    build_attach_snapshot,
    build_run_state_snapshot,
)
from teaagent.run_store import RunStore
from teaagent.tui import TeaAgentTUI


def test_build_run_state_includes_liveness_fields() -> None:
    events = [
        {'event_type': 'run_started', 'payload': {'task': 't'}},
        {
            'event_type': 'heartbeat',
            'created_at': '2026-06-09T00:00:00Z',
            'payload': {'tick': 1},
        },
    ]
    snapshot = build_run_state_snapshot(
        events,
        'run1',
        liveness={
            'updated_at': '2026-06-09T00:00:10Z',
            'age_seconds': 5.0,
            'stale': False,
        },
    )
    payload = snapshot.to_dict()
    assert payload['liveness_age_seconds'] == 5.0
    assert not payload['liveness_stale']


def test_build_run_state_includes_git_sandbox_and_cost() -> None:
    events = [
        {
            'event_type': 'run_started',
            'payload': {'task': 't', 'permission_mode': 'read-only'},
        },
        {
            'event_type': 'git_sandbox_started',
            'payload': {
                'success': True,
                'auto_stash': True,
                'branch_name': 'teaagent-sandbox-run1',
                'original_branch': 'main',
                'stash_id': 'stash@{0}',
            },
        },
        {
            'event_type': 'heartbeat',
            'created_at': '2026-06-09T00:00:00Z',
            'payload': {'tick': 2},
        },
        {
            'event_type': 'git_sandbox_resolved',
            'payload': {'resolution': 'merge', 'success': True},
        },
        {
            'event_type': 'run_completed',
            'payload': {'answer': 'ok', 'cost_cents': 42.5},
        },
    ]
    snapshot = build_run_state_snapshot(events, 'run1', undo_available=True)
    payload = snapshot.to_dict()

    assert payload['schema_version'] == RUN_STATE_SCHEMA_VERSION
    assert payload['status'] == 'completed'
    assert payload['cost_cents'] == 42.5
    assert payload['permission_mode'] == 'read-only'
    assert payload['undo_available']
    assert payload['git_sandbox'] is not None
    assert payload['git_sandbox']['resolution'] == 'merge'


def test_build_run_state_discloses_undo_shell_partial() -> None:
    shell_events = [
        {'event_type': 'run_started', 'payload': {'task': 't'}},
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'c1',
                'tool_name': 'workspace_run_shell_mutate',
                'arguments': {'command': 'echo hi >> f.txt'},
            },
        },
        {'event_type': 'run_completed', 'payload': {'answer': 'ok'}},
    ]
    shell = build_run_state_snapshot(
        shell_events, 'run1', undo_available=True
    ).to_dict()
    assert shell['undo_available'] is True
    assert shell['undo_shell_partial'] is True

    file_events = [
        {'event_type': 'run_started', 'payload': {'task': 't'}},
        {
            'event_type': 'tool_call_completed',
            'payload': {
                'call_id': 'c1',
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'f.txt'},
            },
        },
        {'event_type': 'run_completed', 'payload': {'answer': 'ok'}},
    ]
    file_only = build_run_state_snapshot(
        file_events, 'run2', undo_available=True
    ).to_dict()
    assert file_only['undo_available'] is True
    # Conditional key: absent (not falsely present) when no shell mutation occurred.
    assert 'undo_shell_partial' not in file_only


def test_build_attach_snapshot_exposes_run_state_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger('attach-run')
        audit.record(
            'run_started', 'attach-run', task='attach', permission_mode='prompt'
        )
        audit.record('heartbeat', 'attach-run', tick=1, interval_seconds=0.1)
        audit.record('run_completed', 'attach-run', answer='ok')

        snapshot = build_attach_snapshot(store, 'attach-run')
        assert snapshot['run_id'] == 'attach-run'
        assert snapshot['event_count'] == 3
        assert snapshot['run_state']['schema_version'] == RUN_STATE_SCHEMA_VERSION
        assert snapshot['pending_approval'] is None


def test_cli_and_tui_status_return_identical_run_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        audit = store.audit_logger('parity-run')
        audit.record('run_started', 'parity-run', task='parity')
        audit.record('heartbeat', 'parity-run', tick=1, interval_seconds=0.1)
        audit.record(
            'git_sandbox_started',
            'parity-run',
            success=True,
            auto_stash=False,
            branch_name='teaagent-sandbox-parity-run',
            original_branch='main',
        )
        audit.record('run_completed', 'parity-run', answer='done', cost_cents=10.0)

        cli_out = io.StringIO()
        with redirect_stdout(cli_out):
            code = main(['agent', 'status', 'parity-run', '--root', tmp])
        assert code == 0
        cli_payload = json.loads(cli_out.getvalue())

        tui_out: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=tui_out.append,
        )
        assert tui.handle_command('status parity-run')
        tui_payload = json.loads(tui_out[-1])

        assert cli_payload == tui_payload
        assert cli_payload['schema_version'] == RUN_STATE_SCHEMA_VERSION
        assert 'git_sandbox' in cli_payload


def test_build_run_state_includes_warnings_approvals_and_token_pressure() -> None:
    events = [
        {'event_type': 'run_started', 'payload': {'task': 't'}},
        {
            'event_type': 'budget_warning',
            'payload': {'message': 'approaching budget'},
        },
        {
            'event_type': 'tool_call_pending_approval',
            'payload': {
                'call_id': 'call-456',
                'tool_name': 'execute_command',
                'arguments': {'cmd': 'ls'},
            },
        },
        {
            'event_type': 'heartbeat',
            'payload': {
                'input_tokens': 180000,
                'output_tokens': 10000,
            },
        },
    ]
    snapshot = build_run_state_snapshot(events, 'run2')
    payload = snapshot.to_dict()

    assert payload['warnings'] == ['approaching budget']
    assert payload['pending_approval'] is not None
    assert payload['pending_approval']['call_id'] == 'call-456'
    assert payload['pending_approval']['tool_name'] == 'execute_command'
    assert payload['token_pressure'] == 'red'
