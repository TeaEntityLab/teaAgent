# test-type: behavior
"""Pin dogfood findings G35 and G27.

G35: an ``mcp serve`` stdio session must survive a ``tools/call`` for an
unregistered tool by emitting a JSON-RPC ``-32602`` error frame and continuing
to serve subsequent requests, instead of raising out of the read loop and
killing the connection.

G27: ``mcp trust allow``/``deny`` with ``TEAAGENT_MCP_TRUST_KEY`` unset must
return the family's classified error (rc 1, message naming the env var) rather
than raising through the generic ``Unexpected error`` handler.
"""

from __future__ import annotations

import argparse
import io
import json

from teaagent.cli._handlers._mcp_trust import mcp_trust_allow_command
from teaagent.mcp_server import serve_mcp_stdio
from teaagent.workspace_tools import build_workspace_tool_registry


def test_stdio_session_survives_unknown_tool_call(tmp_path, capsys) -> None:
    """Second frame -> -32602; the third valid call still succeeds."""
    (tmp_path / 'hello.txt').write_text('hi', encoding='utf-8')
    registry = build_workspace_tool_registry(str(tmp_path))

    frames = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
        {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {'name': 'nonexistent_tool', 'arguments': {}},
        },
        {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': 'workspace_read_file',
                'arguments': {'path': 'hello.txt'},
            },
        },
    ]
    reader = io.StringIO('\n'.join(json.dumps(frame) for frame in frames) + '\n')
    writer = io.StringIO()

    rc = serve_mcp_stdio(registry, stdin=reader, stdout=writer)

    assert rc == 0
    lines = [line for line in writer.getvalue().splitlines() if line]
    assert len(lines) == 3

    initialize, unknown, valid = (json.loads(line) for line in lines)
    assert initialize['id'] == 1 and 'result' in initialize

    assert unknown['id'] == 2
    assert unknown['error']['code'] == -32602
    assert unknown['error']['message'] == "tool 'nonexistent_tool' is not registered"

    assert valid['id'] == 3
    assert valid['result']['isError'] is False
    text = json.loads(valid['result']['content'][0]['text'])
    assert text['content'] == 'hi'


def test_trust_allow_missing_key_returns_classified_error(
    tmp_path, capsys, monkeypatch
) -> None:
    """Unset key -> rc 1 and a classified message naming the env var, no raise."""
    monkeypatch.delenv('TEAAGENT_MCP_TRUST_KEY', raising=False)
    args = argparse.Namespace(root=str(tmp_path), server='demo', tools=['t'])

    rc = mcp_trust_allow_command(args)

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['ok'] is False
    assert 'TEAAGENT_MCP_TRUST_KEY' in payload['error']
