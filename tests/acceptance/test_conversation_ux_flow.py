"""WS1-006: Conversation UX acceptance tests."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from teaagent.cli import main
from teaagent.run_receipt import build_run_receipt
from teaagent.run_store import RunResult, RunStore


def _seed_pending_run(root: Path) -> None:
    config = root / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')
    store = RunStore(root)
    audit = store.audit_logger('run-ux')
    audit.record('run_started', 'run-ux', task='update docs', cost_cents=10)
    audit.record(
        'tool_call_pending_approval',
        'run-ux',
        call_id='call-ux',
        tool_name='workspace_write_file',
        reason='needs approval',
        arguments={'path': 'docs/cli.md'},
        annotations={'destructive': True},
    )
    store.logger_for_result(
        RunResult(
            run_id='run-ux',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
            cost_cents=10,
        ),
        audit,
    )


def test_approval_pending_human_display(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--human', '--root', str(tmp_path)]) == 0
    text = out.getvalue()
    assert 'workspace_write_file' in text
    assert 'docs/cli.md' in text
    assert 'destructive' in text


def test_agent_status_progress_human(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-ux',
                    '--progress',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    text = out.getvalue()
    assert 'Phase: pending_approval' in text
    assert 'Budget:' in text


def test_run_receipt_includes_cost_and_audit_path(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    store = RunStore(tmp_path)
    receipt = build_run_receipt(store, 'run-ux', str(tmp_path))
    assert 'Goal: update docs' in receipt
    assert 'Audit log:' in receipt


def test_agent_status_progress_json(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-ux',
                    '--progress',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    payload = json.loads(out.getvalue())
    assert payload['phase'] == 'pending_approval'
    assert payload['run_id'] == 'run-ux'
