from __future__ import annotations

import io
import json
from unittest import mock

from teaagent.acp_adapter import run_acp_server


def test_acp_stdio_loop_emits_json_rpc_error_on_handler_failure() -> None:
    registry = mock.Mock()
    registry.get.side_effect = RuntimeError('boom')

    stdin = io.StringIO(
        json.dumps(
            {
                'jsonrpc': '2.0',
                'id': 7,
                'method': 'tools/list',
                'params': {},
            }
        )
        + '\n'
    )
    stdout = io.StringIO()

    with (
        mock.patch('sys.stdin', stdin),
        mock.patch('sys.stdout', stdout),
        mock.patch('teaagent.acp_adapter.ACPServer') as server_cls,
    ):
        server = mock.Mock()
        server.handle_request.side_effect = RuntimeError('boom')
        server_cls.return_value = server
        run_acp_server(registry, mock.Mock())

    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload['jsonrpc'] == '2.0'
    assert payload['id'] == 7
    assert payload['error']['code'] == -32603
    assert 'boom' in payload['error']['message']
