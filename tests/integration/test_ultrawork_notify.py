"""IT: Ultrawork completion notification.

When a background worker stops, NotifyConfig triggers a webhook POST and/or
executes a shell command.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import patch

from teaagent.notify import NotifyConfig, fire_notification
from teaagent.ultrawork import UltraworkStore, WorkerRecord

_RECEIVED: list[dict] = []


class _NotifyHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        _RECEIVED.append(body)
        self.send_response(200)
        self.end_headers()


def _start_server():
    server = HTTPServer(('127.0.0.1', 0), _NotifyHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}/notify'


# ---------------------------------------------------------------------------
# NotifyConfig + fire_notification
# ---------------------------------------------------------------------------


def test_fire_notification_webhook_delivers(tmp_path):
    server, url = _start_server()
    _RECEIVED.clear()
    try:
        cfg = NotifyConfig(webhook_url=url)
        rec = WorkerRecord(
            worker_id='w1',
            command=['teaagent', 'agent', 'run', 'gpt', 'task'],
            log_path=str(tmp_path / 'w1.log'),
            pid=12345,
            started_at='2026-01-01T00:00:00+00:00',
        )
        fire_notification(cfg, rec, event='stopped')
        import time

        time.sleep(0.05)
        assert len(_RECEIVED) == 1
        assert _RECEIVED[0].get('worker_id') == 'w1'
        assert _RECEIVED[0].get('event') == 'stopped'
    finally:
        server.shutdown()


def test_fire_notification_shell_command_executed(tmp_path):
    cfg = NotifyConfig(shell_command='echo "worker done"')
    rec = WorkerRecord(
        worker_id='w2',
        command=['cmd'],
        log_path=str(tmp_path / 'w2.log'),
        pid=999,
        started_at='2026-01-01T00:00:00+00:00',
    )
    calls: list[Any] = []
    with patch('subprocess.run', side_effect=lambda *a, **kw: calls.append((a, kw))):
        fire_notification(cfg, rec, event='stopped')
    assert len(calls) == 1
    assert 'echo' in calls[0][0][0]


def test_fire_notification_webhook_failure_silent():
    cfg = NotifyConfig(webhook_url='http://127.0.0.1:1/unreachable')
    rec = WorkerRecord(
        worker_id='w3',
        command=['cmd'],
        log_path='/dev/null',
        pid=1,
        started_at='2026-01-01T00:00:00+00:00',
    )
    # Must not raise
    fire_notification(cfg, rec, event='stopped')


def test_fire_notification_both_webhook_and_shell(tmp_path):
    server, url = _start_server()
    _RECEIVED.clear()
    try:
        cfg = NotifyConfig(webhook_url=url, shell_command='true')
        rec = WorkerRecord(
            worker_id='w4',
            command=['cmd'],
            log_path=str(tmp_path / 'w4.log'),
            pid=1,
            started_at='2026-01-01T00:00:00+00:00',
        )
        shell_calls: list = []
        with patch(
            'subprocess.run', side_effect=lambda *a, **kw: shell_calls.append(1)
        ):
            fire_notification(cfg, rec, event='stopped')
        import time

        time.sleep(0.05)
        assert len(shell_calls) == 1
        assert len(_RECEIVED) >= 1
    finally:
        server.shutdown()


def test_notify_config_defaults():
    cfg = NotifyConfig()
    assert cfg.webhook_url is None
    assert cfg.shell_command is None


# ---------------------------------------------------------------------------
# UltraworkStore.stop fires notification
# ---------------------------------------------------------------------------


def test_ultrawork_store_stop_fires_webhook(tmp_path):
    server, url = _start_server()
    _RECEIVED.clear()
    try:
        cfg = NotifyConfig(webhook_url=url)
        store = UltraworkStore(root=tmp_path, notify_config=cfg)
        rec = store.start(['python', '-c', 'import time; time.sleep(60)'])
        import time

        time.sleep(0.05)
        store.stop(rec.worker_id)
        time.sleep(0.1)
        assert any(r.get('worker_id') == rec.worker_id for r in _RECEIVED)
    finally:
        server.shutdown()
