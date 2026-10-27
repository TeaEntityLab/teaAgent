# test-type: behavior
"""Exit-code fallback for dead background runs (U-P1-17).

When the child was already reaped by another waiter, the exit code is lost.
The audit log's last terminal event is authoritative for outcome; the
exit_code=0 fallback is only valid for run_completed and must be marked as
derived so operators can see it is not a real reaped code.
"""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.ergonomics.background_run import BackgroundRunStore

_DEAD_PID = 2_147_483_645


def _seed_dead_run(
    store: BackgroundRunStore, background_id: str, run_id: str, terminal: str
) -> Path:
    """Seed a dead, already-reaped background record plus its audit log."""
    log_path = store.dir / f'{background_id}.log'
    log_path.write_text('', encoding='utf-8')
    record = {
        'background_id': background_id,
        'pid': _DEAD_PID,
        'command': ['noop'],
        'started_at': '2026-09-15T00:00:00+00:00',
        'log_path': str(log_path),
        'run_id': run_id,
    }
    record_path = store.dir / f'{background_id}.json'
    record_path.write_text(json.dumps(record), encoding='utf-8')

    runs_dir = store.root / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                'event_type': 'run_started',
                'run_id': run_id,
                'timestamp': '2026-09-15T00:00:00+00:00',
                'payload': {},
            }
        ),
        json.dumps(
            {
                'event_type': terminal,
                'run_id': run_id,
                'timestamp': '2026-09-15T00:00:01+00:00',
                'payload': {},
            }
        ),
    ]
    (runs_dir / f'{run_id}.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return record_path


def test_failed_run_fallback_does_not_fabricate_exit_zero(tmp_path: Path) -> None:
    """A dead run whose last terminal event is run_failed keeps exit_code None."""
    store = BackgroundRunStore(tmp_path)
    _seed_dead_run(store, 'bg-fallback-failed', 'fallback-failed-run', 'run_failed')

    rows = store.list()
    row = next(r for r in rows if r['background_id'] == 'bg-fallback-failed')

    assert row['alive'] is False
    assert row.get('exit_code') is None
    assert not row.get('exit_code_derived')
    assert not row.get('orphaned')


def test_completed_run_fallback_is_marked_derived(tmp_path: Path) -> None:
    """A dead run whose last terminal event is run_completed gets derived exit 0."""
    store = BackgroundRunStore(tmp_path)
    _seed_dead_run(
        store, 'bg-fallback-completed', 'fallback-completed-run', 'run_completed'
    )

    rows = store.list()
    row = next(r for r in rows if r['background_id'] == 'bg-fallback-completed')

    assert row['alive'] is False
    assert row.get('exit_code') == 0
    assert row.get('exit_code_derived') is True
    assert not row.get('orphaned')


def test_exit_code_derived_is_not_persisted(tmp_path: Path) -> None:
    """The derived marker never reaches the record file on disk."""
    store = BackgroundRunStore(tmp_path)
    record_path = _seed_dead_run(
        store, 'bg-fallback-persist', 'fallback-persist-run', 'run_completed'
    )

    shown = store.get('bg-fallback-persist')
    assert shown.get('exit_code_derived') is True

    on_disk = json.loads(record_path.read_text(encoding='utf-8'))
    assert 'exit_code_derived' not in on_disk
    assert 'alive' not in on_disk


def test_stop_does_not_persist_derived_exit_code(tmp_path: Path) -> None:
    """Stopping a dead, completed record must not store the derived 0."""
    store = BackgroundRunStore(tmp_path)
    record_path = _seed_dead_run(store, 'bg-stop', 'run-stop-1', 'run_completed')
    store.stop('bg-stop')
    on_disk = json.loads(record_path.read_text())
    assert 'exit_code' not in on_disk or on_disk['exit_code'] is None
    assert 'exit_code_derived' not in on_disk
