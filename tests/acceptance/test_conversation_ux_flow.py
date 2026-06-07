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


def test_receipt_includes_cost_state(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    store = RunStore(tmp_path)
    receipt = build_run_receipt(store, 'run-ux', str(tmp_path))
    assert 'Cost:' in receipt
    assert '$' in receipt or 'cents' in receipt


def test_receipt_includes_status_and_progress(tmp_path: Path) -> None:
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
    assert 'Phase:' in text
    assert 'Budget:' in text


def _seed_full_run(root: Path) -> None:
    config = root / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "anthropic"\n', encoding='utf-8')
    store = RunStore(root)
    audit = store.audit_logger('run-full')
    audit.record(
        'run_started',
        'run-full',
        task='refactor auth module',
        provider='anthropic',
        model='claude-sonnet',
        cost_cents=10,
    )
    audit.record(
        'tool_call_started',
        'run-full',
        tool_name='workspace_read_file',
        arguments={'path': 'src/auth.py'},
    )
    audit.record(
        'tool_call_completed',
        'run-full',
        tool_name='workspace_read_file',
        arguments={'path': 'src/auth.py'},
    )
    audit.record(
        'tool_call_started',
        'run-full',
        tool_name='workspace_write_file',
        arguments={'path': 'src/auth.py'},
        annotations={'destructive': True},
    )
    audit.record(
        'tool_call_pending_approval',
        'run-full',
        call_id='call-aa',
        tool_name='workspace_write_file',
        arguments={'path': 'src/auth.py'},
        reason='destructive tool requires approval',
        annotations={'destructive': True},
        created_at='2026-06-06T10:00:00+00:00',
    )
    audit.record(
        'approval_granted',
        'run-full',
        call_id='call-aa',
        tool_name='workspace_write_file',
        scope='run-full',
    )
    audit.record(
        'tool_call_completed',
        'run-full',
        tool_name='workspace_write_file',
        arguments={'path': 'src/auth.py'},
    )
    audit.record(
        'tool_call_started',
        'run-full',
        tool_name='workspace_run_shell_mutate',
        arguments={'command': 'pytest tests/test_auth.py -v'},
    )
    audit.record(
        'tool_call_completed',
        'run-full',
        tool_name='workspace_run_shell_mutate',
        arguments={'command': 'pytest tests/test_auth.py -v'},
    )
    audit.record(
        'tool_call_started',
        'run-full',
        tool_name='pytest',
        arguments={},
    )
    audit.record(
        'tool_call_completed',
        'run-full',
        tool_name='pytest',
        arguments={},
    )
    audit.record(
        'run_paused',
        'run-full',
        reason='operator interrupt',
    )
    audit.record(
        'run_completed',
        'run-full',
        cost_cents=47,
    )
    store.logger_for_result(
        RunResult(
            run_id='run-full',
            final_answer=None,
            iterations=3,
            tool_calls=5,
            status='success',
            cost_cents=47,
        ),
        audit,
    )


def test_cost_display_includes_spent_and_cap(tmp_path: Path) -> None:
    _seed_full_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-full',
                    '--evidence',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    text = out.getvalue()
    assert 'Cost:' in text
    assert '47 cents' in text
    assert 'budget cap:' in text


def test_receipt_uses_background_resume_vocabulary(tmp_path: Path) -> None:
    _seed_full_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-full',
                    '--evidence',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    text = out.getvalue()
    assert 'Resume/checkpoint:' in text
    assert 'checkpointed_suspension' in text


def test_full_receipt_end_to_end_all_fields(tmp_path: Path) -> None:
    _seed_full_run(tmp_path)
    store = RunStore(tmp_path)
    receipt = build_run_receipt(store, 'run-full', str(tmp_path))
    assert 'Run receipt: run-full' in receipt
    assert 'Status: success' in receipt
    assert 'Goal: refactor auth module' in receipt
    assert 'Provider/model: anthropic / claude-sonnet' in receipt
    assert 'Cost:' in receipt
    assert 'Audit log:' in receipt
    assert 'Resume/checkpoint:' in receipt
    assert 'Tools used' in receipt
    assert 'workspace_read_file' in receipt
    assert 'workspace_write_file' in receipt
    assert 'workspace_run_shell_mutate' in receipt
    assert 'Files touched:' in receipt
    assert 'src/auth.py' in receipt
    assert 'Commands run:' in receipt
    assert 'Tests run:' in receipt
    assert 'Approvals:' in receipt
    assert 'workspace_write_file: granted' in receipt
    assert 'Rollback/undo:' in receipt


def test_tui_progress_includes_resume_vocabulary(tmp_path: Path) -> None:
    _seed_full_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-full',
                    '--progress',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    text = out.getvalue()
    assert 'Phase:' in text
    assert 'Budget:' in text
    assert 'next' in text.lower() or 'action' in text.lower()


def test_evidence_human_combined_produces_complete_receipt(tmp_path: Path) -> None:
    _seed_full_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'agent',
                    'status',
                    'run-full',
                    '--evidence',
                    '--human',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    text = out.getvalue()
    assert 'Run receipt: run-full' in text
    assert 'Status: success' in text
    assert 'Goal: refactor auth module' in text
    assert 'Provider/model: anthropic / claude-sonnet' in text
    assert 'Cost:' in text
    assert 'Audit log:' in text
    assert 'Resume/checkpoint:' in text


def test_approval_pending_display_includes_age_and_expiry(tmp_path: Path) -> None:
    _seed_pending_run(tmp_path)
    out = StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--human', '--root', str(tmp_path)]) == 0
    text = out.getvalue()
    assert 'workspace_write_file' in text
    assert 'age:' in text
    assert 'expires:' in text
