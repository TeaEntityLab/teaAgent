from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from teaagent.ergonomics.background_run import BackgroundRunStore, _run_id_from_log


def test_run_id_from_log_parses_agent_result(tmp_path: Path) -> None:
    log = tmp_path / 'worker.log'
    log.write_text(
        json.dumps({'run_id': 'run-bg-1', 'status': 'completed'}) + '\n',
        encoding='utf-8',
    )
    assert _run_id_from_log(log) == 'run-bg-1'


def test_background_list_reports_dead_pid(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    bg_dir = store.dir
    log_path = bg_dir / 'dead.log'
    log_path.write_text('', encoding='utf-8')
    record = {
        'background_id': 'dead01',
        'pid': 2_147_483_647,
        'command': ['noop'],
        'started_at': '2026-05-22T00:00:00+00:00',
        'log_path': str(log_path),
    }
    (bg_dir / 'dead01.json').write_text(json.dumps(record), encoding='utf-8')
    rows = store.list()
    assert len(rows) == 1
    assert rows[0]['alive'] is False


def test_background_start_echo_command(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [sys.executable, '-c', "print('ok')"],
        label='echo-smoke',
    )
    assert record.background_id
    shown = store.get(record.background_id)
    assert shown['label'] == 'echo-smoke'
    assert 'log_path' in shown


def test_background_reconciles_completed_child_process(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [
            sys.executable,
            '-c',
            "import json; print(json.dumps({'run_id':'run-live-bg','status':'completed'}))",
        ],
        label='live-smoke',
    )
    shown = store.get(record.background_id)
    deadline = time.time() + 5.0
    while shown['alive'] and time.time() < deadline:
        time.sleep(0.05)
        shown = store.get(record.background_id)

    assert shown['alive'] is False
    assert shown['exit_code'] == 0
    assert shown['run_id'] == 'run-live-bg'
    assert shown['stopped_at']


def test_background_show_includes_run_id_from_log(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    bg_id = 'show01'
    log_path = store.dir / f'{bg_id}.log'
    log_path.write_text(
        json.dumps({'run_id': 'run-from-log', 'status': 'completed'}) + '\n',
        encoding='utf-8',
    )
    (store.dir / f'{bg_id}.json').write_text(
        json.dumps(
            {
                'background_id': bg_id,
                'pid': 2_147_483_646,
                'command': ['noop'],
                'started_at': '2026-05-22T00:00:00+00:00',
                'log_path': str(log_path),
            }
        ),
        encoding='utf-8',
    )
    shown = store.get(bg_id)
    assert shown['run_id'] == 'run-from-log'
    assert shown['alive'] is False


def test_readonly_background_dead_record_does_not_write_file(tmp_path: Path) -> None:
    """Verify that readonly background get/list returns enriched data but doesn't write."""
    bg_dir = tmp_path / '.teaagent' / 'background'
    bg_dir.mkdir(parents=True)
    log_path = bg_dir / 'dead-readonly.log'
    log_path.write_text('', encoding='utf-8')

    # Create a dead process record without stopped_at
    record = {
        'background_id': 'dead-readonly',
        'pid': 2_147_483_647,
        'command': ['noop'],
        'started_at': '2026-05-22T00:00:00+00:00',
        'log_path': str(log_path),
    }
    record_path = bg_dir / 'dead-readonly.json'
    original_content = json.dumps(record)
    record_path.write_text(original_content, encoding='utf-8')

    # Get record with readonly store
    readonly_store = BackgroundRunStore(tmp_path, readonly=True)
    shown = readonly_store.get('dead-readonly')

    # Should return enriched data with stopped_at
    assert shown['alive'] is False
    assert 'stopped_at' in shown

    # But file should not be modified
    current_content = record_path.read_text(encoding='utf-8')
    assert current_content == original_content
    assert 'stopped_at' not in json.loads(current_content)

    # Same for list()
    rows = readonly_store.list()
    assert len(rows) == 1
    assert rows[0]['alive'] is False
    assert 'stopped_at' in rows[0]

    # File still not modified
    current_content = record_path.read_text(encoding='utf-8')
    assert current_content == original_content


def test_background_stop_and_logs(tmp_path: Path) -> None:
    import sys

    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [sys.executable, '-c', 'import time; time.sleep(5.0)'],
        label='sleep-smoke',
    )
    assert record.background_id

    # Check log tail initially (should be empty or contain nothing yet)
    logs = store.logs(record.background_id)
    assert logs['background_id'] == record.background_id

    # Stop the worker
    stopped = store.stop(record.background_id, timeout_seconds=1.0)
    assert stopped['alive'] is False
    assert stopped['stop_signal'] in ('SIGTERM', 'SIGKILL')
