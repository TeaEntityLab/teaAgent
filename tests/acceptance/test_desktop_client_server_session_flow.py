"""Client-server surface: MCP HTTP server, session lifecycle, CLI session list."""

from __future__ import annotations

import io
import json
import tempfile
import threading
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.mcp_client import MCPHTTPClient
from teaagent.mcp_http import build_mcp_http_server
from teaagent.workspace_tools import build_workspace_tool_registry


def test_mcp_http_client_server_and_cli_session_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'hello.txt').write_text('client-server', encoding='utf-8')
        server, sessions = build_mcp_http_server(
            build_workspace_tool_registry(root),
            host='127.0.0.1',
            port=0,
            auth_token='desktop-token',
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address[:2]
        try:
            client = MCPHTTPClient(
                f'http://{host}:{port}/mcp',
                auth_token='desktop-token',
            )
            client.initialize()
            tools = {tool['name'] for tool in client.list_tools()}
            result = client.call_tool('workspace_read_file', {'path': 'hello.txt'})
            session_id = client.session_id
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        assert 'workspace_read_file' in tools
        assert not result['isError']
        assert 'client-server' in result['content'][0]['text']
        assert session_id is not None
        assert not sessions.has(session_id)

        with redirect_stdout(io.StringIO()):
            setup_code = main(
                [
                    'setup',
                    '--root',
                    tmp,
                    '--provider',
                    'gpt',
                    '--api-key',
                    'sk-desktop',
                    '--permission-mode',
                    'read-only',
                ]
            )
        assert setup_code == 0
        out = io.StringIO()
        with redirect_stdout(out):
            list_code = main(['session', 'list', '--root', tmp])
        assert list_code == 0
        assert isinstance(json.loads(out.getvalue()), list)
