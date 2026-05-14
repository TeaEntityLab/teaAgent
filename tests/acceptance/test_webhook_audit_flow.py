"""AC-NEW-12: Webhook audit event delivery flow.

As a fleet operator, I want to subscribe to audit events via webhook so my
SIEM or monitoring system receives every important event in real time.

Acceptance criteria:
- Every audit event fires the webhook during a run.
- HMAC signature is present and verifiable.
- Event filter restricts which event types are delivered.
- Webhook failure does not abort the run.
- Extra custom headers are included in each request.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.webhook_sink import WebhookAuditSink


class _Collector(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []
    lock = threading.Lock()

    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        with self.__class__.lock:
            self.__class__.received.append(
                {
                    'body': body,
                    'headers': dict(self.headers),
                }
            )
        self.send_response(200)
        self.end_headers()


def _start() -> tuple[HTTPServer, str]:
    _Collector.received = []
    server = HTTPServer(('127.0.0.1', 0), _Collector)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}/'


class _StubAdapter:
    provider = 'stub'

    def complete(self, request):  # type: ignore[override]
        from teaagent.llm import LLMResponse

        return LLMResponse(
            provider='stub',
            model='stub',
            content='{"type":"final","content":"done"}',
        )


def test_run_events_delivered_to_webhook(tmp_path):
    server, url = _start()
    try:
        sink = WebhookAuditSink(url, raise_on_error=True)
        audit = AuditLogger()
        audit.add_sink(sink)
        adapter = _StubAdapter()
        config = ChatAgentConfig.from_root(tmp_path)
        result = run_chat_agent(
            task='hello', adapter=adapter, config=config, audit=audit
        )

        assert result.status == 'completed'
        event_types = {json.loads(r['body'])['event_type'] for r in _Collector.received}
        assert 'run_started' in event_types
        assert 'run_completed' in event_types
    finally:
        server.shutdown()


def test_webhook_hmac_verifiable(tmp_path):
    server, url = _start()
    secret = 'my-webhook-secret'
    try:
        sink = WebhookAuditSink(url, secret=secret, raise_on_error=True)
        audit = AuditLogger()
        audit.add_sink(sink)
        audit.record('run_started', 'run-test')

        req = _Collector.received[0]
        # Headers may be lowercase-normalised by BaseHTTPRequestHandler
        headers_lower = {k.lower(): v for k, v in req['headers'].items()}
        sig = headers_lower.get('x-teaagent-signature-256', '')
        assert sig.startswith('sha256='), f'got sig header: {sig!r}'
        expected = hmac.new(secret.encode(), req['body'], hashlib.sha256).hexdigest()
        assert sig == f'sha256={expected}'
    finally:
        server.shutdown()


def test_webhook_event_filter_limits_delivery(tmp_path):
    server, url = _start()
    try:
        sink = WebhookAuditSink(
            url, event_filter={'run_completed'}, raise_on_error=True
        )
        audit = AuditLogger()
        audit.add_sink(sink)
        adapter = _StubAdapter()
        config = ChatAgentConfig.from_root(tmp_path)
        run_chat_agent(task='hello', adapter=adapter, config=config, audit=audit)

        types = {json.loads(r['body'])['event_type'] for r in _Collector.received}
        assert types == {'run_completed'}, f'only run_completed expected, got {types}'
    finally:
        server.shutdown()


def test_webhook_failure_does_not_abort_run(tmp_path):
    """Webhook pointing at a closed port must not abort the agent run."""
    sink = WebhookAuditSink('http://127.0.0.1:1/', raise_on_error=False)
    audit = AuditLogger()
    audit.add_sink(sink)
    adapter = _StubAdapter()
    config = ChatAgentConfig.from_root(tmp_path)
    result = run_chat_agent(task='hello', adapter=adapter, config=config, audit=audit)
    assert result.status == 'completed'
