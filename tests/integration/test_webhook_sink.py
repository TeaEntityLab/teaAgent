"""IT-8: WebhookAuditSink delivers events to an HTTP endpoint.

Spins up a minimal HTTP server in-process to capture requests and verify
content, headers, and HMAC signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.webhook_sink import WebhookAuditSink


class _CapturingHandler(BaseHTTPRequestHandler):
    captured: list[dict[str, Any]] = []
    lock = threading.Lock()

    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        with self.__class__.lock:
            self.__class__.captured.append(
                {
                    'body': body,
                    'headers': dict(self.headers),
                }
            )
        self.send_response(200)
        self.end_headers()


def _start_server() -> tuple[HTTPServer, str]:
    _CapturingHandler.captured = []
    server = HTTPServer(('127.0.0.1', 0), _CapturingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}/'


def test_webhook_delivers_event():
    server, url = _start_server()
    try:
        sink = WebhookAuditSink(url, raise_on_error=True)
        audit = AuditLogger()
        audit.add_sink(sink)
        audit.record('run_completed', 'run-001', answer='hello')

        captured = _CapturingHandler.captured
        assert len(captured) == 1
        payload = json.loads(captured[0]['body'])
        assert payload['event_type'] == 'run_completed'
    finally:
        server.shutdown()


def test_webhook_hmac_signature():
    server, url = _start_server()
    secret = 'test-secret'
    try:
        sink = WebhookAuditSink(url, secret=secret, raise_on_error=True)
        audit = AuditLogger()
        audit.add_sink(sink)
        audit.record('tool_call_started', 'run-002', tool_name='read_file')

        captured = _CapturingHandler.captured
        assert len(captured) == 1
        # Headers from BaseHTTPRequestHandler may be lowercase on some Python versions
        headers_lower = {k.lower(): v for k, v in captured[0]['headers'].items()}
        sig_header = headers_lower.get('x-teaagent-signature-256', '')
        assert sig_header.startswith('sha256='), f'got sig header: {sig_header!r}'
        body = captured[0]['body']
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert sig_header == f'sha256={expected_sig}'
    finally:
        server.shutdown()


def test_webhook_event_filter():
    server, url = _start_server()
    try:
        sink = WebhookAuditSink(
            url, event_filter={'run_completed'}, raise_on_error=True
        )
        audit = AuditLogger()
        audit.add_sink(sink)
        audit.record('run_started', 'run-003')  # filtered out
        audit.record('run_completed', 'run-003', answer='ok')  # delivered

        captured = _CapturingHandler.captured
        assert len(captured) == 1
        payload = json.loads(captured[0]['body'])
        assert payload['event_type'] == 'run_completed'
    finally:
        server.shutdown()


def test_webhook_failure_does_not_crash_run():
    """Even when raise_on_error=False and server is down, the run continues."""
    sink = WebhookAuditSink('http://127.0.0.1:1/', raise_on_error=False)
    audit = AuditLogger()
    audit.add_sink(sink)
    # Must not raise even though the server is unreachable
    event = audit.record('run_started', 'run-004')
    assert event.event_type == 'run_started'
