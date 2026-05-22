from __future__ import annotations

import json
import sys
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
