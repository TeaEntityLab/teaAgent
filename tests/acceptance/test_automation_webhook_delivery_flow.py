"""Test module for automation webhook delivery.

This module tests the webhook delivery mechanism for automations, which posts
collector results to a configured webhook URL when delivery=webhook is set.
This enables external systems to receive automation results via HTTP webhooks.

Key concepts tested:
- Webhook Delivery: delivery=webhook posts results to configured URL
- HTTP Server: Test server receives and validates webhook payloads
- HMAC Signature: Webhooks are signed with X-TeaAgent-Signature-256 header
- Configuration: Webhook URL and secret are in .teaagent/config.toml
- Collector Integration: Webhook delivery works with collector scripts
- Skip Handling: Webhooks are delivered even when wake_agent=false

Acceptance Criteria:
- AC1: Webhook delivery posts collector results to configured URL
- AC2: Webhook payload includes automation_id, status, and collector output
- AC3: Webhook includes HMAC signature in X-TeaAgent-Signature-256 header
- AC4: Webhook URL and secret are configured in .teaagent/config.toml
- AC5: Webhook delivery works when wake_agent=false (skipped_no_wake)
- AC6: Signature format is sha256=...

Technical Details:
- automation_webhook_url configures the webhook endpoint
- automation_webhook_secret configures the HMAC signing key
- Webhook payload is JSON with automation metadata and collector results
- HMAC-SHA256 signature ensures payload integrity
- Webhook is delivered after collector execution, regardless of wake_agent
- HTTP POST with JSON body and signature header

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Webhook spec: /docs/specs/automation_webhooks.md
"""

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
