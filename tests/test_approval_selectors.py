"""Tests for readable pending approval selectors."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from teaagent.approval_selectors import (
    classify_risk_class,
    collect_pending_approval_views,
    format_pending_approvals,
    resolve_selector,
    summarize_tool_arguments,
)
from teaagent.cli import main
from teaagent.run_store import RunResult, RunStore


def test_summarize_tool_arguments_prefers_path_and_command() -> None:
    assert summarize_tool_arguments({'path': 'src/foo.py'}) == 'src/foo.py'
    assert summarize_tool_arguments({'command': 'rm -rf /tmp/x'}) == 'rm -rf /tmp/x'


def test_classify_risk_class_uses_annotations() -> None:
    assert (
        classify_risk_class(
            tool_name='workspace_write_file',
            annotations={'destructive': True},
            reason_code=None,
        )
        == 'destructive'
    )
    assert (
        classify_risk_class(
            tool_name='workspace_read_file',
            annotations={'read_only': True},
            reason_code=None,
        )
        == 'read-only'
    )


def test_collect_and_format_pending_approval_views(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-pending')
    audit.record('run_started', 'run-pending', task='write docs')
    audit.record(
        'tool_call_pending_approval',
        'run-pending',
        call_id='call-123',
        tool_name='workspace_write_file',
        arguments={'path': 'docs/cli.md', 'content': 'x'},
        reason='destructive tool requires approval',
        annotations={'destructive': True},
        created_at='2026-06-06T10:00:00+00:00',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-pending',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )

    views = collect_pending_approval_views(store, limit=10)
    assert len(views) == 1
    view = views[0]
    assert view.selector == 1
    assert view.tool_name == 'workspace_write_file'
    assert view.path_summary == 'docs/cli.md'
    assert view.risk_class == 'destructive'
    # expires_at should be a valid future ISO date (current time + expiry window)
    assert 'T' in view.expires_at
    assert view.expires_at.endswith('+00:00')

    text = format_pending_approvals(views)
    assert 'Approve "workspace_write_file" — docs/cli.md' in text
    assert 'Why: destructive tool requires approval' in text
    assert 'approval approve --selector 1' in text
    assert resolve_selector(views, 1) is view
    assert resolve_selector(views, 99) is None


def test_approval_pending_human_and_selector_approve(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('provider = "gpt"\n', encoding='utf-8')

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-pending')
    audit.record('run_started', 'run-pending', task='write docs')
    audit.record(
        'tool_call_pending_approval',
        'run-pending',
        call_id='call-123',
        tool_name='workspace_write_file',
    )
    store.logger_for_result(
        RunResult(
            run_id='run-pending',
            final_answer=None,
            iterations=1,
            tool_calls=1,
            status='pending_approval',
        ),
        audit,
    )

    out = StringIO()
    with redirect_stdout(out):
        assert main(['approval', 'pending', '--human', '--root', str(tmp_path)]) == 0
    human = out.getvalue()
    assert 'Approve "workspace_write_file"' in human
    assert 'approval approve --selector 1' in human

    out = StringIO()
    with redirect_stdout(out):
        assert (
            main(
                [
                    'approval',
                    'approve',
                    '--selector',
                    '1',
                    '--root',
                    str(tmp_path),
                ]
            )
            == 0
        )
    payload = json.loads(out.getvalue())
    assert payload['status'] == 'approved'
    assert payload['call_id'] == 'call-123'
