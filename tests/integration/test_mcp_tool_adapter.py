"""IT-4: MCPToolAdapter registers remote MCP tools into ToolRegistry.

Uses a live ``A2ADiscoveryServer`` + ``MCPHTTPClient`` pattern to spin up a
minimal MCP-compatible server in-process, then verifies that
``register_mcp_tools`` correctly reflects the remote tool surface.

The test is gated on the MCP HTTP server being importable (always true) and
the network being loopback-only.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from teaagent.mcp_tool_adapter import register_mcp_tools
from teaagent.tools import ToolRegistry

_FAKE_TOOLS = [
    {
        'name': 'remote_echo',
        'description': 'Echoes the input back.',
        'input_schema': {
            'type': 'object',
            'properties': {'message': {'type': 'string'}},
            'required': ['message'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False},
    },
    {
        'name': 'remote_write',
        'description': 'Writes data.',
        'input_schema': {'type': 'object', 'properties': {}},
        'annotations': {'readOnlyHint': False, 'destructiveHint': True},
    },
]


class _FakeMCPHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # suppress server logs in tests
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        method = body.get('method', '')

        if method == 'initialize':
            resp = {
                'jsonrpc': '2.0',
                'id': body.get('id'),
                'result': {'serverInfo': {}},
            }
            session_id = 'test-session-1'
        elif method == 'tools/list':
            resp = {
                'jsonrpc': '2.0',
                'id': body.get('id'),
                'result': {'tools': _FAKE_TOOLS},
            }
            session_id = self.headers.get('Mcp-Session-Id', 'test-session-1')
        elif method == 'tools/call':
            tool_name = body.get('params', {}).get('name', '')
            resp = {
                'jsonrpc': '2.0',
                'id': body.get('id'),
                'result': {
                    'content': [{'type': 'text', 'text': f'called:{tool_name}'}],
                    'isError': False,
                },
            }
            session_id = self.headers.get('Mcp-Session-Id', 'test-session-1')
        else:
            self.send_response(404)
            self.end_headers()
            return

        raw = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Mcp-Session-Id', session_id)
        self.end_headers()
        self.wfile.write(raw)

    def do_DELETE(self) -> None:
        self.send_response(204)
        self.end_headers()


def _start_fake_mcp_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(('127.0.0.1', 0), _FakeMCPHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{port}/mcp'


def test_register_mcp_tools_discovers_all_tools():
    server, endpoint = _start_fake_mcp_server()
    try:
        registry = ToolRegistry()
        names = register_mcp_tools(registry, endpoint=endpoint)
        assert set(names) == {'remote_echo', 'remote_write'}
        # Tools are in registry
        assert registry.get('remote_echo') is not None
        assert registry.get('remote_write') is not None
    finally:
        server.shutdown()


def test_register_mcp_tools_annotations_inferred():
    server, endpoint = _start_fake_mcp_server()
    try:
        registry = ToolRegistry()
        register_mcp_tools(registry, endpoint=endpoint)
        echo_tool = registry.get('remote_echo')
        write_tool = registry.get('remote_write')
        assert echo_tool.annotations.read_only is True
        assert echo_tool.annotations.destructive is False
        assert write_tool.annotations.destructive is True
    finally:
        server.shutdown()


def test_register_mcp_tools_name_prefix_filter():
    server, endpoint = _start_fake_mcp_server()
    try:
        registry = ToolRegistry()
        names = register_mcp_tools(registry, endpoint=endpoint, name_prefix='remote_e')
        assert names == ['remote_echo']
        assert registry.get('remote_echo') is not None
        try:
            registry.get('remote_write')
            raise AssertionError('remote_write should not be registered')
        except KeyError:
            pass
    finally:
        server.shutdown()
