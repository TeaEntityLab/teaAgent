from __future__ import annotations

import json
import sys
from typing import Any, Iterable, Optional, TextIO

from teaagent.errors import AgentHarnessError
from teaagent.tools import ToolRegistry

PROTOCOL_VERSION = '2024-11-05'
SERVER_INFO = {'name': 'teaagent', 'version': '0.1.0'}


def handle_mcp_request(
    registry: ToolRegistry, request: dict[str, Any]
) -> Optional[dict[str, Any]]:
    request_id = request.get('id')
    method = request.get('method')
    params = request.get('params') or {}

    if request_id is None:
        return None

    if method == 'initialize':
        return _ok(
            request_id,
            {
                'protocolVersion': PROTOCOL_VERSION,
                'capabilities': {'tools': {}},
                'serverInfo': SERVER_INFO,
            },
        )
    if method == 'tools/list':
        return _ok(request_id, {'tools': _tools_payload(registry)})
    if method == 'tools/call':
        return _call_tool(registry, request_id, params)
    return _error(request_id, -32601, f"method '{method}' not found")


def serve_mcp_stdio(
    registry: ToolRegistry,
    *,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
) -> int:
    reader = stdin or sys.stdin
    writer = stdout or sys.stdout
    for line in _iter_jsonl_lines(reader):
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_mcp_request(registry, request)
        if response is not None:
            writer.write(json.dumps(response, ensure_ascii=False) + '\n')
            writer.flush()
    return 0


def _iter_jsonl_lines(reader: TextIO) -> Iterable[str]:
    for raw in reader:
        line = raw.strip()
        if line:
            yield line


def _tools_payload(registry: ToolRegistry) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for tool in registry.mcp_metadata():
        payload.append(
            {
                'name': tool['name'],
                'description': tool['description'],
                'inputSchema': tool['input_schema'],
                'annotations': tool['annotations'],
            }
        )
    return payload


def _call_tool(
    registry: ToolRegistry, request_id: Any, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get('name')
    arguments = params.get('arguments') or {}
    if not isinstance(name, str):
        return _error(request_id, -32602, "tools/call requires string 'name'")
    if not isinstance(arguments, dict):
        return _error(request_id, -32602, "tools/call requires object 'arguments'")
    try:
        result = registry.execute(name, arguments)
    except AgentHarnessError as exc:
        return _ok(
            request_id,
            {
                'content': [{'type': 'text', 'text': str(exc)}],
                'isError': True,
            },
        )
    return _ok(
        request_id,
        {
            'content': [
                {
                    'type': 'text',
                    'text': json.dumps(result, ensure_ascii=False, sort_keys=True),
                }
            ],
            'isError': False,
        },
    )


def _ok(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': {'code': code, 'message': message},
    }
