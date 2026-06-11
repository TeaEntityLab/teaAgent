"""Test module for MCP (Model Context Protocol) client flow.

This module tests the integration between TeaAgent's MCP client and server,
which implements the Model Context Protocol for tool interoperability. The MCP
protocol enables standardized tool discovery, invocation, and session management
across different AI systems.

Key concepts tested:
- MCP Server Initialization: HTTP server with tool registry and authentication
- Client Authentication: Token-based auth to prevent unauthorized access
- Tool Discovery: Clients can list available tools from the server
- Tool Invocation: Clients can call tools with parameters and receive results
- Session Management: Sessions are tracked and cleaned up on client close
- Error Handling: Unauthorized clients are rejected with appropriate errors

Acceptance Criteria:
- AC1: MCP server starts successfully with workspace tool registry
- AC2: Unauthenticated clients cannot initialize or call tools
- AC3: Authenticated clients can initialize and receive server info
- AC4: Authenticated clients can list available tools
- AC5: Authenticated clients can call tools and receive results
- AC6: Sessions are properly tracked and cleaned up on client close
- AC7: Server handles concurrent clients via threading

Technical Details:
- Uses MCPHTTPClient for HTTP-based MCP protocol communication
- build_mcp_http_server creates a threaded HTTP server with auth
- build_workspace_tool_registry provides workspace tools (read, write, search)
- Auth tokens are required for all operations
- Sessions are tracked in a session manager
- Server runs on a dynamic port (port=0) for test isolation

References:
- MCP spec: https://modelcontextprotocol.io/
- TeaAgent MCP implementation: /docs/architecture/mcp_integration.md
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest

from teaagent.mcp_client import MCPClientError, MCPHTTPClient
from teaagent.mcp_http import build_mcp_http_server
from teaagent.workspace_tools import build_workspace_tool_registry


def test_mcp_client_auth_session_list_call_and_close_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'hello.txt').write_text('hello mcp', encoding='utf-8')
        server, sessions = build_mcp_http_server(
            build_workspace_tool_registry(root),
            host='127.0.0.1',
            port=0,
            auth_token='secret-token',
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address[:2]
        try:
            unauthenticated = MCPHTTPClient(f'http://{host}:{port}/mcp')
            with pytest.raises(MCPClientError):
                unauthenticated.initialize()

            client = MCPHTTPClient(
                f'http://{host}:{port}/mcp', auth_token='secret-token'
            )
            server_info = client.initialize()['serverInfo']
            tools = client.list_tools()
            result = client.call_tool('workspace_read_file', {'path': 'hello.txt'})
            session_id = client.session_id
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        # Verify server info contains expected name
        assert server_info['name'] == 'teaagent', (
            'Expected server name to be "teaagent"'
        )
        # Verify workspace_read_file tool is available
        assert 'workspace_read_file' in {tool['name'] for tool in tools}, (
            'Expected workspace_read_file to be in available tools'
        )
        # Verify tool call succeeded without error
        assert not result['isError'], 'Expected tool call to succeed without error'
        # Verify tool result contains expected content
        assert 'hello mcp' in result['content'][0]['text'], (
            'Expected tool result to contain "hello mcp"'
        )
        # Verify session_id was assigned
        assert session_id is not None, 'Expected session_id to be assigned'
        # Verify session was cleaned up after client close
        assert not sessions.has(session_id), (
            'Expected session to be cleaned up after client close'
        )
