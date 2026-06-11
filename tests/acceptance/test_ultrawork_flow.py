from __future__ import annotations

import io
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout

from teaagent import UltraworkStore
from teaagent.cli import main


def test_ultrawork_start_list_show_logs_and_stop_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = UltraworkStore(tmp)
        record = store.start(
            [
                sys.executable,
                '-c',
                'import time; print("worker ready", flush=True); time.sleep(5)',
            ],
            label='acceptance-worker',
        )
        time.sleep(0.2)

        list_out = io.StringIO()
        with redirect_stdout(list_out):
            list_code = main(['ultrawork', 'list', '--root', tmp])

        show_out = io.StringIO()
        with redirect_stdout(show_out):
            show_code = main(['ultrawork', 'show', record.worker_id, '--root', tmp])

        logs_out = io.StringIO()
        with redirect_stdout(logs_out):
            logs_code = main(['ultrawork', 'logs', record.worker_id, '--root', tmp])

        stop_out = io.StringIO()
        with redirect_stdout(stop_out):
            stop_code = main(['ultrawork', 'stop', record.worker_id, '--root', tmp])

        list_payload = json.loads(list_out.getvalue())
        show_payload = json.loads(show_out.getvalue())
        logs_payload = json.loads(logs_out.getvalue())
        stop_payload = json.loads(stop_out.getvalue())

        assert list_code == 0
        assert show_code == 0
        assert logs_code == 0
        assert stop_code == 0
        assert list_payload[0]['worker_id'] == record.worker_id
        assert show_payload['label'] == 'acceptance-worker'
        assert show_payload['alive']
        assert 'worker ready' in logs_payload['content']
        assert not stop_payload['alive']
        assert stop_payload['stop_signal'] in {'SIGTERM', 'SIGKILL'}
