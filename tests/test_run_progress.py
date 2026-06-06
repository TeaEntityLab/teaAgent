"""Tests for run progress summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from teaagent.run_progress import (
    build_run_progress_summary,
    format_run_progress_summary,
)
from teaagent.run_store import RunStore


def _write_run(root: Path, run_id: str, events: list[dict]) -> None:
    path = RunStore(root).run_path(run_id)
    path.write_text(
        '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n',
        encoding='utf-8',
    )


def test_build_run_progress_summary_for_running_run(tmp_path: Path) -> None:
    events = [
        {
            'event_type': 'run_started',
            'created_at': '2026-06-06T10:00:00+00:00',
            'payload': {
                'task': 'refactor module',
                'max_estimated_cost_cents': 500,
            },
        },
        {
            'event_type': 'tool_call_started',
            'created_at': '2026-06-06T10:00:10+00:00',
            'payload': {
                'tool_name': 'workspace_read_file',
                'call_id': 'read-1',
            },
        },
    ]
    _write_run(tmp_path, 'run-progress', events)
    store = RunStore(tmp_path)

    summary = build_run_progress_summary(
        store,
        'run-progress',
        now=datetime(2026, 6, 6, 10, 0, 30, tzinfo=timezone.utc),
    )
    assert summary.phase == 'running'
    assert summary.last_tool == 'workspace_read_file'
    assert summary.budget_cap_cents == 500
    assert summary.budget_remaining_cents == 500
    assert summary.elapsed_seconds == 30.0

    text = format_run_progress_summary(summary)
    assert 'Phase: running' in text
    assert 'workspace_read_file' in text
    assert '500c remaining' in text


def test_build_run_progress_summary_for_pending_approval(tmp_path: Path) -> None:
    events = [
        {
            'event_type': 'run_started',
            'created_at': '2026-06-06T10:00:00+00:00',
            'payload': {'task': 'write docs'},
        },
        {
            'event_type': 'tool_call_pending_approval',
            'created_at': '2026-06-06T10:00:05+00:00',
            'payload': {
                'call_id': 'call-1',
                'tool_name': 'workspace_write_file',
            },
        },
        {
            'event_type': 'run_paused',
            'created_at': '2026-06-06T10:00:05+00:00',
            'payload': {'status': 'pending_approval'},
        },
    ]
    _write_run(tmp_path, 'run-pending', events)
    store = RunStore(tmp_path)

    summary = build_run_progress_summary(store, 'run-pending')
    assert summary.phase == 'pending_approval'
    assert 'approval pending --human' in summary.next_action
