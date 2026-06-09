"""Tests for human-readable run receipts."""

from __future__ import annotations

import json
import tempfile

from teaagent.evidence_summary import build_evidence_summary
from teaagent.run_receipt import (
    build_run_receipt,
    extract_run_receipt_context,
    format_run_receipt,
)
from teaagent.run_store import RunStore


def _write_run(root: str, run_id: str, events: list[dict]) -> None:
    path = RunStore(root).run_path(run_id)
    path.write_text(
        '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n',
        encoding='utf-8',
    )


def test_format_run_receipt_includes_required_sections():
    events = [
        {
            'event_type': 'run_started',
            'timestamp': '2026-06-06T10:00:00Z',
            'payload': {
                'task': 'fix failing test',
                'provider': 'anthropic',
                'model': 'claude-sonnet',
            },
        },
        {
            'event_type': 'tool_call_completed',
            'timestamp': '2026-06-06T10:01:00Z',
            'payload': {
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'foo.py', 'content': 'x'},
            },
        },
        {
            'event_type': 'run_completed',
            'timestamp': '2026-06-06T10:05:00Z',
            'payload': {'cost_cents': 42},
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = 'receipt-001'
        _write_run(tmpdir, run_id, events)
        store = RunStore(tmpdir)
        summary = build_evidence_summary(store, run_id, tmpdir)
        context = extract_run_receipt_context(
            events,
            run_id=run_id,
            root=tmpdir,
            store=store,
        )
        text = format_run_receipt(summary, context)
        assert 'Run receipt: receipt-001' in text
        assert 'Goal: fix failing test' in text
        assert 'Provider/model: anthropic / claude-sonnet' in text
        assert 'Audit log:' in text
        assert 'workspace_write_file' in text
        assert 'Cost:' in text


def test_build_run_receipt_for_missing_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStore(tmpdir)
        text = build_run_receipt(store, 'missing-run', tmpdir)
        assert 'Status: not found' in text


def test_derive_resume_state_suspended_from_pending_approval():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'tool_call_pending_approval'},
        {'event_type': 'run_paused'},
    ]
    summary = RunEvidenceSummary(run_id='r1', status='pending_approval')
    assert _derive_resume_state(events, summary=summary) == 'checkpointed_suspension'


def test_derive_resume_state_suspended_from_run_paused_event():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'run_paused'},
    ]
    summary = RunEvidenceSummary(run_id='r2', status='running')
    assert _derive_resume_state(events, summary=summary) == 'checkpointed_suspension'


def test_derive_resume_state_resumable_from_run_suspended():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'run_suspended'},
    ]
    summary = RunEvidenceSummary(run_id='r3', status='running')
    assert _derive_resume_state(events, summary=summary) == 'resumable_session'


def test_derive_resume_state_resumable_from_suspension_created():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'suspension_created'},
    ]
    summary = RunEvidenceSummary(run_id='r4', status='running')
    assert _derive_resume_state(events, summary=summary) == 'resumable_session'


def test_derive_resume_state_checkpoint_available():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'run_completed'},
    ]
    summary = RunEvidenceSummary(run_id='r5', status='success', rollback_available=True)
    assert _derive_resume_state(events, summary=summary) == 'checkpoint_available'


def test_derive_resume_state_none():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _derive_resume_state

    events: list[dict] = [
        {'event_type': 'run_started'},
        {'event_type': 'run_completed'},
    ]
    summary = RunEvidenceSummary(
        run_id='r6', status='success', rollback_available=False
    )
    assert _derive_resume_state(events, summary=summary) == 'none'


def test_format_cost_unlimited_budget():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _format_cost

    summary = RunEvidenceSummary(
        run_id='r', total_cost_cents=50, cost_state='unlimited'
    )
    text = _format_cost(summary)
    assert '50 cents' in text
    assert 'unlimited' in text
    assert 'budget cap: unlimited' in text


def test_format_cost_not_set_budget():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _format_cost

    summary = RunEvidenceSummary(
        run_id='r',
        total_cost_cents=30,
        cost_state='estimated',
        budget_cap_cents=None,
    )
    text = _format_cost(summary)
    assert '30 cents' in text
    assert 'estimated' in text
    assert 'budget cap: not set' in text


def test_format_cost_specific_cents_budget():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _format_cost

    summary = RunEvidenceSummary(
        run_id='r',
        total_cost_cents=75,
        cost_state='provider_reported',
        budget_cap_cents=500,
    )
    text = _format_cost(summary)
    assert '75 cents' in text
    assert 'provider_reported' in text
    assert 'budget cap: 500 cents' in text


def test_format_cost_zero_cents_specific_budget():
    from teaagent.evidence_summary import RunEvidenceSummary
    from teaagent.run_receipt import _format_cost

    summary = RunEvidenceSummary(
        run_id='r',
        total_cost_cents=0,
        cost_state='unknown',
        budget_cap_cents=1000,
    )
    text = _format_cost(summary)
    assert '0 cents' in text
    assert 'unknown' in text
    assert 'budget cap: 1000 cents' in text


def test_emit_run_completion_output_human_replaces_json(capsys) -> None:
    import argparse

    from teaagent.cli._handlers._agent.run import _emit_run_completion_output

    with tempfile.TemporaryDirectory() as tmpdir:
        events = [
            {
                'event_type': 'run_started',
                'payload': {'task': 'ship receipt', 'provider': 'stub', 'model': 'm'},
            },
            {'event_type': 'run_completed', 'payload': {'cost_cents': 5}},
        ]
        run_id = 'emit-human'
        path = RunStore(tmpdir).run_path(run_id)
        path.write_text(
            '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n',
            encoding='utf-8',
        )
        store = RunStore(tmpdir)
        args = argparse.Namespace(
            root=tmpdir,
            human=True,
            json_stream=False,
        )
        _emit_run_completion_output(
            args,
            store=store,
            run_id=run_id,
            payload={'run_id': run_id, 'status': 'completed'},
        )
        captured = capsys.readouterr()
        assert 'Run receipt: emit-human' in captured.out
        assert 'Goal: ship receipt' in captured.out
        assert captured.out.strip().startswith('Run receipt:')
        assert 'emit-human' not in captured.err


def test_emit_run_completion_output_tty_receipt_on_stderr(monkeypatch, capsys) -> None:
    import argparse

    from teaagent.cli._handlers._agent.run import _emit_run_completion_output

    monkeypatch.setattr('sys.stderr.isatty', lambda: True)

    with tempfile.TemporaryDirectory() as tmpdir:
        events = [
            {
                'event_type': 'run_started',
                'payload': {'task': 'tty receipt'},
            },
            {'event_type': 'run_completed', 'payload': {}},
        ]
        run_id = 'emit-tty'
        path = RunStore(tmpdir).run_path(run_id)
        path.write_text(
            '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n',
            encoding='utf-8',
        )
        store = RunStore(tmpdir)
        args = argparse.Namespace(root=tmpdir, human=False, json_stream=False)
        _emit_run_completion_output(
            args,
            store=store,
            run_id=run_id,
            payload={'run_id': run_id, 'status': 'completed'},
        )
        captured = capsys.readouterr()
        assert '"run_id"' in captured.out
        assert 'Run receipt: emit-tty' in captured.err
