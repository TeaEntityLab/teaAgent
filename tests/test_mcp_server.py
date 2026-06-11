from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from teaagent import handle_mcp_request, serve_mcp_stdio
from teaagent.workspace_tools import build_workspace_tool_registry


def test_initialize_returns_protocol_and_capabilities() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}
        )

        assert response['id'] == 1
        assert 'protocolVersion' in response['result']
        assert response['result']['serverInfo']['name'] == 'teaagent'


def test_tools_list_returns_workspace_tools() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
        )

        tools = response['result']['tools']
        names = {tool['name'] for tool in tools}
        assert 'workspace_read_file' in names
        assert 'inputSchema' in tools[0]


def test_tools_call_executes_read_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'hello.txt').write_text('hi', encoding='utf-8')
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 3,
                'method': 'tools/call',
                'params': {
                    'name': 'workspace_read_file',
                    'arguments': {'path': 'hello.txt'},
                },
            },
        )

        payload = response['result']
        assert not payload['isError']
        text = json.loads(payload['content'][0]['text'])
        assert text['content'] == 'hi'


def test_tools_call_returns_is_error_for_validation_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry,
            {
                'jsonrpc': '2.0',
                'id': 4,
                'method': 'tools/call',
                'params': {'name': 'workspace_read_file', 'arguments': {}},
            },
        )

        assert response['result']['isError']


def test_unknown_method_returns_method_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = build_workspace_tool_registry(tmp)

        response = handle_mcp_request(
            registry, {'jsonrpc': '2.0', 'id': 5, 'method': 'ping'}
        )

        assert response['error']['code'] == -32601


def test_serve_mcp_stdio_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'hello.txt').write_text('hi', encoding='utf-8')
        registry = build_workspace_tool_registry(tmp)
        stdin = io.StringIO(
            '\n'.join(
                [
                    json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}),
                    json.dumps(
                        {
                            'jsonrpc': '2.0',
                            'id': 2,
                            'method': 'tools/call',
                            'params': {
                                'name': 'workspace_read_file',
                                'arguments': {'path': 'hello.txt'},
                            },
                        }
                    ),
                    '',
                ]
            )
        )
        stdout = io.StringIO()

        exit_code = serve_mcp_stdio(registry, stdin=stdin, stdout=stdout)

        lines = [line for line in stdout.getvalue().splitlines() if line]
        assert exit_code == 0
        assert len(lines) == 2
        init_response = json.loads(lines[0])
        call_response = json.loads(lines[1])
        assert init_response['id'] == 1
        assert not call_response['result']['isError']
