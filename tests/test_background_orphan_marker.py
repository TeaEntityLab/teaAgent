# test-type: behavior
"""Focused tests for the BG-001 §3.3 orphan marker in background_run.py."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

from teaagent.ergonomics.background_run import BackgroundRunStore


def _wait_for_dead(store: BackgroundRunStore, background_id: str) -> dict[str, object]:
    deadline = time.time() + 5.0
    while time.time() < deadline:
        shown = store.get(background_id)
        if not shown['alive']:
            return shown
        time.sleep(0.05)
    return store.get(background_id)


def test_killed_background_run_marked_orphaned(tmp_path: Path) -> None:
    """A SIGKILLed background run with a run_id but no exit file is orphaned."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [sys.executable, '-c', 'import time; time.sleep(30)'],
        label='killed-for-orphan',
    )
    store.update_run_id(record.background_id, 'orphan-run-killed')

    os.kill(record.pid, signal.SIGKILL)
    shown = _wait_for_dead(store, record.background_id)

    assert shown['alive'] is False
    assert 'stop_signal' not in shown
    assert shown.get('exit_code') != 0
    assert shown['orphaned'] is True

    rows = store.list()
    assert rows[0]['orphaned'] is True


def test_clean_exit_not_orphaned(tmp_path: Path) -> None:
    """A process that exits 0 is not orphaned."""
    store = BackgroundRunStore(tmp_path)
    record = store.start([sys.executable, '-c', 'import sys; sys.exit(0)'])
    shown = _wait_for_dead(store, record.background_id)

    assert shown['alive'] is False
    assert shown['exit_code'] == 0
    assert not shown.get('orphaned')


def test_missing_audit_record_marked_orphaned(tmp_path: Path) -> None:
    """A dead run with a run_id but no terminal audit file is orphaned."""
    store = BackgroundRunStore(tmp_path)
    bg_dir = store.dir
    log_path = bg_dir / 'orphan.log'
    log_path.write_text('', encoding='utf-8')
    record = {
        'background_id': 'bg-orphan-audit',
        'pid': 2_147_483_647,
        'command': ['noop'],
        'started_at': '2026-09-15T00:00:00+00:00',
        'log_path': str(log_path),
        'run_id': 'missing-audit-run',
    }
    (bg_dir / 'bg-orphan-audit.json').write_text(json.dumps(record), encoding='utf-8')

    rows = store.list()
    assert len(rows) == 1
    assert rows[0]['alive'] is False
    assert rows[0].get('orphaned') is True
    assert rows[0].get('exit_code') is None


def test_run_completed_audit_backfills_exit_code(tmp_path: Path) -> None:
    """A dead run with a run_completed audit record is clean and not orphaned."""
    store = BackgroundRunStore(tmp_path)
    bg_dir = store.dir
    log_path = bg_dir / 'clean.log'
    log_path.write_text('', encoding='utf-8')
    record = {
        'background_id': 'bg-clean-audit',
        'pid': 2_147_483_646,
        'command': ['noop'],
        'started_at': '2026-09-15T00:00:00+00:00',
        'log_path': str(log_path),
        'run_id': 'clean-audit-run',
    }
    (bg_dir / 'bg-clean-audit.json').write_text(json.dumps(record), encoding='utf-8')

    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True)
    audit_line = json.dumps(
        {
            'event_type': 'run_completed',
            'run_id': 'clean-audit-run',
            'timestamp': '2026-09-15T00:00:01+00:00',
            'payload': {'answer': 'ok'},
        }
    )
    (runs_dir / 'clean-audit-run.jsonl').write_text(audit_line + '\n', encoding='utf-8')

    rows = store.list()
    assert rows[0]['alive'] is False
    assert rows[0].get('exit_code') == 0
    assert not rows[0].get('orphaned')


def test_stopped_background_not_orphaned(tmp_path: Path) -> None:
    """A background run stopped via the store is not marked orphaned."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [sys.executable, '-c', 'import time; time.sleep(20)'],
        label='stopped-not-orphan',
    )
    stopped = store.stop(record.background_id, timeout_seconds=0.5)

    assert stopped['alive'] is False
    assert stopped.get('stop_signal') is not None
    assert not stopped.get('orphaned')
