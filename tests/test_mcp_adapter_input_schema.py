# test-type: contract
"""G-P1-6: the MCP adapter must read the wire key ``inputSchema``.

MCP ``tools/list`` manifests carry the argument schema under the camelCase key
``inputSchema``. Before this fix the adapter only read ``input_schema``, so
every real remote tool was registered with the permissive default schema and
argument validation never ran.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import pytest

from teaagent.errors import ToolValidationError
from teaagent.mcp_tool_adapter import register_mcp_tools
from teaagent.types import ToolRegistry

_DEFAULT_SCHEMA = {'type': 'object', 'properties': {}}
_REQUIRED_MESSAGE_SCHEMA = {
    'type': 'object',
    'properties': {'message': {'type': 'string'}},
    'required': ['message'],
}


class _RecordingMCPHandler(BaseHTTPRequestHandler):
    """Minimal MCP HTTP server that serves ``tools`` and records every method."""

    tools: ClassVar[list[dict[str, Any]]] = []
    methods_seen: ClassVar[list[str]] = []

    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        method = body.get('method', '')
        type(self).methods_seen.append(method)
        if method == 'initialize':
            result: dict[str, Any] = {'serverInfo': {}}
        elif method == 'tools/list':
            result = {'tools': type(self).tools}
        elif method == 'tools/call':
            result = {
                'content': [{'type': 'text', 'text': 'ok'}],
                'isError': False,
            }
        else:
            self.send_response(404)
            self.end_headers()
            return
        raw = json.dumps({'jsonrpc': '2.0', 'id': body.get('id'), 'result': result})
        raw_bytes = raw.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw_bytes)))
        self.send_header('Mcp-Session-Id', 'schema-test-session')
        self.end_headers()
        self.wfile.write(raw_bytes)

    def do_DELETE(self) -> None:
        self.send_response(204)
        self.end_headers()


@pytest.fixture
def mcp_server():
    """Start a loopback MCP server; yields a factory returning (endpoint, methods seen)."""
    servers: list[HTTPServer] = []

    def start(tools: list[dict[str, Any]]) -> tuple[str, list[str]]:
        seen: list[str] = []
        handler = type(
            '_Handler',
            (_RecordingMCPHandler,),
            {'tools': tools, 'methods_seen': seen},
        )
        server = HTTPServer(('127.0.0.1', 0), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f'http://127.0.0.1:{server.server_address[1]}/mcp', seen

    yield start
    for server in servers:
        server.shutdown()


def _manifest(name: str, **schema_keys: Any) -> dict[str, Any]:
    tool: dict[str, Any] = {'name': name, 'description': f'{name} tool'}
    tool.update(schema_keys)
    return tool


def test_wire_key_inputschema_is_read(mcp_server):
    endpoint, seen = mcp_server(
        [_manifest('remote_say', inputSchema=_REQUIRED_MESSAGE_SCHEMA)]
    )
    registry = ToolRegistry()
    register_mcp_tools(registry, endpoint=endpoint)
    assert registry.get('remote_say').input_schema['required'] == ['message']


def test_wire_key_inputschema_is_enforced_before_any_http_call(mcp_server):
    endpoint, seen = mcp_server(
        [_manifest('remote_say', inputSchema=_REQUIRED_MESSAGE_SCHEMA)]
    )
    registry = ToolRegistry()
    register_mcp_tools(registry, endpoint=endpoint)

    with pytest.raises(ToolValidationError):
        registry.execute('remote_say', {})

    # Validation must reject the call locally: no tools/call reached the server.
    assert 'tools/call' not in seen


def test_wire_key_inputschema_valid_arguments_still_dispatch(mcp_server):
    endpoint, seen = mcp_server(
        [_manifest('remote_say', inputSchema=_REQUIRED_MESSAGE_SCHEMA)]
    )
    registry = ToolRegistry()
    register_mcp_tools(registry, endpoint=endpoint)

    result = registry.execute('remote_say', {'message': 'hi'})

    assert result['isError'] is False
    assert 'tools/call' in seen


def test_snake_case_input_schema_still_accepted(mcp_server):
    endpoint, seen = mcp_server(
        [_manifest('remote_say', input_schema=_REQUIRED_MESSAGE_SCHEMA)]
    )
    registry = ToolRegistry()
    register_mcp_tools(registry, endpoint=endpoint)
    assert registry.get('remote_say').input_schema['required'] == ['message']


def test_inputschema_wins_over_snake_case_when_both_present(mcp_server):
    endpoint, seen = mcp_server(
        [
            _manifest(
                'remote_say',
                inputSchema=_REQUIRED_MESSAGE_SCHEMA,
                input_schema=_DEFAULT_SCHEMA,
            )
        ]
    )
    registry = ToolRegistry()
    register_mcp_tools(registry, endpoint=endpoint)
    assert registry.get('remote_say').input_schema['required'] == ['message']


@pytest.mark.parametrize('bad_schema', ['not-a-dict', ['list'], None, 42])
def test_non_dict_schema_falls_back_to_default_with_warning(
    mcp_server, caplog, bad_schema
):
    endpoint, seen = mcp_server([_manifest('remote_bad', inputSchema=bad_schema)])
    registry = ToolRegistry()
    with caplog.at_level(logging.WARNING, logger='teaagent.mcp_tool_adapter'):
        register_mcp_tools(registry, endpoint=endpoint)

    assert registry.get('remote_bad').input_schema == _DEFAULT_SCHEMA
    warnings = [
        r
        for r in caplog.records
        if r.name == 'teaagent.mcp_tool_adapter' and r.levelno == logging.WARNING
    ]
    assert warnings, 'a non-dict input schema must log a warning, not pass silently'
    assert 'remote_bad' in warnings[0].getMessage()


def test_missing_schema_falls_back_to_default_with_warning(mcp_server, caplog):
    endpoint, seen = mcp_server([_manifest('remote_bare')])
    registry = ToolRegistry()
    with caplog.at_level(logging.WARNING, logger='teaagent.mcp_tool_adapter'):
        register_mcp_tools(registry, endpoint=endpoint)

    assert registry.get('remote_bare').input_schema == _DEFAULT_SCHEMA
    assert any('remote_bare' in r.getMessage() for r in caplog.records)
