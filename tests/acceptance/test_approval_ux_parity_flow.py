"""SURF-009: CLI and TUI expose the same pending-approval queue contract."""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch

from teaagent.cli import main
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.integration.approval_parity import (
    APPROVAL_QUEUE_SCHEMA_VERSION,
    build_pending_approvals_snapshot,
)
from teaagent.run_store import RunResult, RunStore
from teaagent.tui import TeaAgentTUI


def _seed_pending_run(root: str, run_id: str = 'approval-parity') -> None:
    store = RunStore(root)
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task='write docs', permission_mode='prompt')
    audit.record(
        'tool_call_pending_approval',
        run_id,
        call_id='call-123',
        tool_name='workspace_write_file',
        arguments={'path': 'docs/cli.md', 'content': 'x'},
        reason='destructive tool requires approval',
        annotations={'destructive': True},
        created_at='2026-06-09T10:00:00+00:00',
    )
    store.logger_for_result(
        RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )


def test_build_pending_approvals_snapshot_matches_shared_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp)
        store = RunStore(tmp)
        snapshot = build_pending_approvals_snapshot(store)

        assert snapshot['schema_version'] == APPROVAL_QUEUE_SCHEMA_VERSION
        assert snapshot['queue_depth'] == 1
        pending = snapshot['pending'][0]
        assert pending['selector'] == 1
        assert pending['run_id'] == 'approval-parity'
        assert pending['call_id'] == 'call-123'
        assert pending['tool_name'] == 'workspace_write_file'
        assert pending['path_summary'] == 'docs/cli.md'
        assert pending['risk_class'] == 'destructive'


def test_cli_and_tui_pending_queue_payloads_match() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp)

        cli_out = io.StringIO()
        with redirect_stdout(cli_out):
            code = main(['approval', 'pending', '--root', tmp])
        assert code == 0
        cli_payload = json.loads(cli_out.getvalue())

        tui_out: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=tui_out.append,
        )
        assert tui.handle_command('approvals pending')
        tui_payload = json.loads(tui_out[-1])

        assert cli_payload['schema_version'] == tui_payload['schema_version']
        assert cli_payload['queue_depth'] == tui_payload['queue_depth']
        assert len(cli_payload['pending']) == len(tui_payload['pending'])
        cli_item = cli_payload['pending'][0]
        tui_item = tui_payload['pending'][0]
        volatile = {'age_seconds'}
        assert {k: v for k, v in cli_item.items() if k not in volatile} == {
            k: v for k, v in tui_item.items() if k not in volatile
        }


def test_tui_selector_approve_targets_same_call_id_as_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp)
        tui_out: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=tui_out.append,
        )
        assert tui.handle_command('approve --selector 1')
        assert 'call-123' in tui.approved_call_ids
        assert any('approved: call-123' in line for line in tui_out)

        cli_out = io.StringIO()
        with redirect_stdout(cli_out):
            code = main(
                [
                    'approval',
                    'approve',
                    '--selector',
                    '1',
                    '--root',
                    tmp,
                ]
            )
        assert code == 0
        cli_payload = json.loads(cli_out.getvalue())
        assert cli_payload['status'] == 'approved'
        assert cli_payload['call_id'] == 'call-123'


def test_tui_approve_resume_grants_scoped_approval_like_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _seed_pending_run(tmp)
        tui_out: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=tui_out.append,
        )
        with patch('teaagent.tui._commands._safe_run_agent_task'):
            assert tui.handle_command('approve --selector 1 --resume')

        store = ApprovalPresetStore(tmp)
        scoped = store.list_scoped_approvals_for_run('approval-parity')
        assert len(scoped) == 1
        assert scoped[0].call_id == 'call-123'
        assert scoped[0].tool_name == 'workspace_write_file'
