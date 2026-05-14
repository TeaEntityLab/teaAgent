"""AC-NEW-9: Remote MCP tool consumption flow.

As a platform engineer, I want to connect TeaAgent to a remote MCP server
and have its tools appear in the tool registry, with approval rules applied
uniformly, so that I can reuse community tools without custom code.

Acceptance criteria:
- ``register_mcp_tools`` discovers all remote tools and registers them.
- Tool annotations from the remote MCP manifest are respected.
- An optional ``name_prefix`` filters which tools are registered.
- Rate-limit rules can be applied uniformly to all remote tools.
- A registered remote tool can be invoked through ``ToolRegistry.execute``.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from teaagent.mcp_tool_adapter import register_mcp_tools
from teaagent.tools import ToolRateLimit, ToolRegistry

_TOOLS = [
    {
        'name': 'gh_list_issues',
        'description': 'List GitHub issues.',
        'input_schema': {'type': 'object', 'properties': {'repo': {'type': 'string'}}},
        'annotations': {'readOnlyHint': True, 'destructiveHint': False},
    },
    {
        'name': 'gh_create_issue',
        'description': 'Create a GitHub issue.',
        'input_schema': {'type': 'object', 'properties': {'title': {'type': 'string'}}},
        'annotations': {'readOnlyHint': False, 'destructiveHint': True},
    },
    {
        'name': 'slack_post',
        'description': 'Post to Slack.',
        'input_schema': {
            'type': 'object',
            'properties': {'message': {'type': 'string'}},
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': True},
    },
]


class _MockMCPHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        method = body.get('method', '')

        if method == 'initialize':
            resp = {'jsonrpc': '2.0', 'id': body.get('id'), 'result': {}}
            session = 'sess-1'
        elif method == 'tools/list':
            resp = {'jsonrpc': '2.0', 'id': body.get('id'), 'result': {'tools': _TOOLS}}
            session = self.headers.get('Mcp-Session-Id', 'sess-1')
        elif method == 'tools/call':
            name = body.get('params', {}).get('name', '')
            resp = {
                'jsonrpc': '2.0',
                'id': body.get('id'),
                'result': {
                    'content': [{'type': 'text', 'text': f'result:{name}'}],
                    'isError': False,
                },
            }
            session = self.headers.get('Mcp-Session-Id', 'sess-1')
        else:
            self.send_response(404)
            self.end_headers()
            return

        raw = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Mcp-Session-Id', session)
        self.end_headers()
        self.wfile.write(raw)

    def do_DELETE(self) -> None:
        self.send_response(204)
        self.end_headers()


def _start() -> tuple[HTTPServer, str]:
    server = HTTPServer(('127.0.0.1', 0), _MockMCPHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{port}/mcp'


def test_all_tools_registered():
    server, endpoint = _start()
    try:
        registry = ToolRegistry()
        names = register_mcp_tools(registry, endpoint=endpoint)
        assert set(names) == {'gh_list_issues', 'gh_create_issue', 'slack_post'}
    finally:
        server.shutdown()


def test_name_prefix_filter():
    server, endpoint = _start()
    try:
        registry = ToolRegistry()
        names = register_mcp_tools(registry, endpoint=endpoint, name_prefix='gh_')
        assert set(names) == {'gh_list_issues', 'gh_create_issue'}
        # slack_post must NOT be registered
        try:
            registry.get('slack_post')
            raise AssertionError('slack_post should not be registered')
        except KeyError:
            pass
    finally:
        server.shutdown()


def test_destructive_annotation_propagated():
    server, endpoint = _start()
    try:
        registry = ToolRegistry()
        register_mcp_tools(registry, endpoint=endpoint)
        assert registry.get('gh_list_issues').annotations.read_only is True
        assert registry.get('gh_create_issue').annotations.destructive is True
    finally:
        server.shutdown()


def test_rate_limit_applied_to_all_remote_tools():
    server, endpoint = _start()
    try:
        registry = ToolRegistry()
        register_mcp_tools(
            registry,
            endpoint=endpoint,
            rate_limit=ToolRateLimit(max_calls=100, window_seconds=60.0),
        )
        for name in ['gh_list_issues', 'gh_create_issue', 'slack_post']:
            tool = registry.get(name)
            assert tool.rate_limit is not None, f'{name} must have rate_limit set'
            assert tool.rate_limit.max_calls == 100
    finally:
        server.shutdown()


def test_remote_tool_callable():
    server, endpoint = _start()
    try:
        registry = ToolRegistry()
        register_mcp_tools(registry, endpoint=endpoint, name_prefix='gh_list')
        result = registry.execute('gh_list_issues', {'repo': 'myorg/myrepo'})
        assert result['isError'] is False
        assert result['content'][0]['text'] == 'result:gh_list_issues'
    finally:
        server.shutdown()
