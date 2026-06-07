"""delivery=webhook posts collector results to the workspace webhook URL."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from teaagent.cli import main


class _HookHandler(BaseHTTPRequestHandler):
    payloads: list[dict[str, object]] = []
    signatures: list[str | None] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        _HookHandler.payloads.append(json.loads(body.decode('utf-8')))
        _HookHandler.signatures.append(self.headers.get('X-TeaAgent-Signature-256'))
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def test_automation_webhook_delivery_flow(tmp_path: Path) -> None:
    _HookHandler.payloads.clear()
    server = HTTPServer(('127.0.0.1', 0), _HookHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    host = server.server_address[0]
    port = server.server_address[1]
    hook_url = f'http://{host}:{port}/automation'

    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True)
    config.write_text(
        f'automation_webhook_url = "{hook_url}"\n'
        'automation_webhook_secret = "acceptance-hmac-secret"\n',
        encoding='utf-8',
    )

    collector = tmp_path / 'collector.py'
    collector.write_text(
        'import json, sys\n'
        'print(json.dumps({"wake_agent": False, "summary": "no changes"}))\n'
        'sys.exit(0)\n',
        encoding='utf-8',
    )
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'webhook-watcher',
                'Run collector and deliver summary via webhook when idle.',
                '--schedule',
                'every 30m',
                '--collector-command',
                f'{sys.executable} {collector}',
                '--delivery',
                'webhook',
                '--acceptance-criteria',
                'Webhook receives collector summary when wake_agent is false.',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

    run_out = io.StringIO()
    with redirect_stdout(run_out):
        run_code = main(
            ['agent', 'automation', 'run', automation_id, '--root', str(tmp_path)]
        )
    assert run_code == 0
    assert json.loads(run_out.getvalue())['status'] == 'skipped_no_wake'
    assert _HookHandler.payloads
    last = _HookHandler.payloads[-1]
    assert last['automation_id'] == automation_id
    assert last['status'] == 'skipped_no_wake'
    assert last['collector']['summary'] == 'no changes'
    assert _HookHandler.signatures[-1] is not None
    assert str(_HookHandler.signatures[-1]).startswith('sha256=')
    server.shutdown()
