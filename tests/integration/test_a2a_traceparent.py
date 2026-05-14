"""IT: A2A delegation carries W3C traceparent header.

Every A2AClient.delegate() call may carry a traceparent header so that the
full multi-agent call tree is visible in distributed tracing backends.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from teaagent.a2a_trace import TraceparentError, generate_traceparent, parse_traceparent
from teaagent.agentcard import A2AClient, A2ATaskResult, AgentCard

_CARD = AgentCard(
    name='trace-agent',
    version='1.0.0',
    description='tracing test',
    capabilities=frozenset(['tool_execution']),
    tools=(),
    endpoint='http://127.0.0.1:0',
)

_RECEIVED_HEADERS: dict[str, str] = {}


class _TraceHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == '/.well-known/agent.json':
            raw = json.dumps(_CARD.to_dict()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        _RECEIVED_HEADERS.clear()
        for key in self.headers:
            _RECEIVED_HEADERS[key.lower()] = self.headers[key]

        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        resp = json.dumps(
            {'agent_name': 'trace-agent', 'output': 'ok', 'task': body.get('task', '')}
        ).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


def _start_server():
    server = HTTPServer(('127.0.0.1', 0), _TraceHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}'


# ---------------------------------------------------------------------------
# generate_traceparent / parse_traceparent
# ---------------------------------------------------------------------------


def test_generate_traceparent_format():
    tp = generate_traceparent()
    parts = tp.split('-')
    assert len(parts) == 4
    version, trace_id, span_id, flags = parts
    assert version == '00'
    assert len(trace_id) == 32
    assert len(span_id) == 16
    assert flags in ('00', '01')


def test_parse_valid_traceparent():
    tp = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
    parsed = parse_traceparent(tp)
    assert parsed['trace_id'] == '4bf92f3577b34da6a3ce929d0e0e4736'
    assert parsed['parent_id'] == '00f067aa0ba902b7'
    assert parsed['flags'] == '01'


def test_parse_invalid_traceparent_raises():
    import pytest

    with pytest.raises(TraceparentError):
        parse_traceparent('bad-format')


def test_generate_then_parse_roundtrip():
    tp = generate_traceparent()
    parsed = parse_traceparent(tp)
    assert len(parsed['trace_id']) == 32
    assert len(parsed['parent_id']) == 16


# ---------------------------------------------------------------------------
# A2AClient injects header
# ---------------------------------------------------------------------------


def test_delegate_injects_traceparent_header():
    server, base_url = _start_server()
    try:
        client = A2AClient(base_url)
        tp = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
        client.delegate('hello', traceparent=tp)
        assert _RECEIVED_HEADERS.get('traceparent') == tp
    finally:
        server.shutdown()


def test_delegate_without_traceparent_no_header():
    server, base_url = _start_server()
    try:
        client = A2AClient(base_url)
        client.delegate('hello')
        assert 'traceparent' not in _RECEIVED_HEADERS
    finally:
        server.shutdown()


def test_delegate_returns_traceparent_in_result():
    server, base_url = _start_server()
    try:
        client = A2AClient(base_url)
        tp = generate_traceparent()
        result = client.delegate('task', traceparent=tp)
        assert isinstance(result, A2ATaskResult)
        # The outbound traceparent is preserved on the result for span continuation
        assert result.traceparent == tp
    finally:
        server.shutdown()


def test_delegate_result_traceparent_none_when_not_set():
    server, base_url = _start_server()
    try:
        client = A2AClient(base_url)
        result = client.delegate('task')
        assert result.traceparent is None
    finally:
        server.shutdown()


def test_generate_traceparent_unique():
    """Every call should produce a different trace ID."""
    tps = {generate_traceparent() for _ in range(20)}
    assert len(tps) == 20
