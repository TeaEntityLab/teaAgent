"""AC-NEW-22: VSCode MCP runtime smoke flow.

As an IDE user, I want the VSCode MCP boot command and provider configuration
to match runtime capabilities, and I need the launched MCP HTTP endpoint to be
usable by a client.

Acceptance criteria:
- VSCode manifest contributes the MCP server command.
- VSCode default provider enum matches runtime provider registry.
- Runtime MCP HTTP endpoint accepts initialize/list/call/close flow.
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from teaagent.llm import available_providers
from teaagent.mcp_client import MCPHTTPClient
from teaagent.mcp_http import build_mcp_http_server
from teaagent.workspace_tools import build_workspace_tool_registry


def test_vscode_mcp_runtime_smoke_flow() -> None:
    root = Path(__file__).resolve().parents[2]
    package_json = root / 'vscode' / 'package.json'
    extension_ts = root / 'vscode' / 'src' / 'extension.ts'

    manifest = json.loads(package_json.read_text(encoding='utf-8'))
    command_ids = {
        cmd.get('command')
        for cmd in manifest.get('contributes', {}).get('commands', [])
        if isinstance(cmd, dict)
    }
    assert 'teaagent.startMcpServer' in command_ids

    source = extension_ts.read_text(encoding='utf-8')
    assert "registerCommand('teaagent.startMcpServer'" in source
    assert "['mcp', 'serve', '--http'" in source

    provider_enum = (
        manifest.get('contributes', {})
        .get('configuration', {})
        .get('properties', {})
        .get('teaagent.defaultProvider', {})
        .get('enum', [])
    )
    assert set(provider_enum) == set(available_providers())

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        (workspace / 'hello.txt').write_text('hello from vscode mcp', encoding='utf-8')
        server, sessions = build_mcp_http_server(
            build_workspace_tool_registry(workspace),
            host='127.0.0.1',
            port=0,
            auth_token='secret-token',
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address[:2]
        try:
            client = MCPHTTPClient(
                f'http://{host}:{port}/mcp', auth_token='secret-token'
            )
            info = client.initialize()['serverInfo']
            tools = client.list_tools()
            result = client.call_tool('workspace_read_file', {'path': 'hello.txt'})
            session_id = client.session_id
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        assert info['name'] == 'teaagent'
        assert 'workspace_read_file' in {tool['name'] for tool in tools}
        assert result['isError'] is False
        assert 'hello from vscode mcp' in result['content'][0]['text']
        assert session_id is not None
        assert sessions.has(session_id) is False
