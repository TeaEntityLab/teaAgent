from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from teaagent import UltraworkStore
from teaagent.cli import main


def _sleep_command(seconds: float) -> list[str]:
    return [sys.executable, '-c', f'import time; time.sleep({seconds})']


def test_start_returns_record_and_persists_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)

        record = store.start(_sleep_command(0.5), label='demo')

        assert len(record.command) == 3
        assert record.label == 'demo'
        assert Path(record.log_path).exists()
        persisted = json.loads(
            (
                Path(tmp) / '.teaagent' / 'background' / f'{record.worker_id}.json'
            ).read_text()
        )
        assert persisted['pid'] == record.pid

        store.stop(record.worker_id)


def test_list_marks_alive_then_dead() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)
        record = store.start(_sleep_command(0.2))

        alive = store.list()
        assert alive[0]['alive']

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if not store.list()[0]['alive']:
                break
            time.sleep(0.05)

        dead = store.list()
        assert not dead[0]['alive']
        assert dead[0]['worker_id'] == record.worker_id


def test_stop_terminates_running_worker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)
        record = store.start(_sleep_command(5.0))

        stopped = store.stop(record.worker_id, timeout_seconds=1.0)

        assert not stopped['alive']
        assert stopped['stop_signal'] in {'SIGTERM', 'SIGKILL'}
        assert not UltraworkStore._is_alive(record.pid)


def test_show_unknown_worker_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp, pytest.raises(FileNotFoundError):
        UltraworkStore(tmp).show('missing')


def test_cli_ultrawork_list_returns_persisted_record() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)
        record = store.start(_sleep_command(0.2))

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['ultrawork', 'list', '--root', tmp])

        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert payload[0]['worker_id'] == record.worker_id

        store.stop(record.worker_id)


def test_cli_ultrawork_stop_marks_record_stopped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)
        record = store.start(_sleep_command(2.0))

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['ultrawork', 'stop', record.worker_id, '--root', tmp])

        payload = json.loads(output.getvalue())
        assert exit_code == 0
        assert not payload['alive']
