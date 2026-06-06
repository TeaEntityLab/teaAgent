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
