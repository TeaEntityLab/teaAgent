from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from teaagent.mcp_client import MCPClientError, MCPHTTPClient
from teaagent.mcp_http import build_mcp_http_server
from teaagent.workspace_tools import build_workspace_tool_registry


class MCPClientFlowAcceptanceTests(unittest.TestCase):
    def test_mcp_client_auth_session_list_call_and_close_flow(self) -> None:
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
                with self.assertRaises(MCPClientError):
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

            self.assertEqual(server_info['name'], 'teaagent')
            self.assertIn('workspace_read_file', {tool['name'] for tool in tools})
            self.assertFalse(result['isError'])
            self.assertIn('hello mcp', result['content'][0]['text'])
            self.assertIsNotNone(session_id)
            assert session_id is not None
            self.assertFalse(sessions.has(session_id))


if __name__ == '__main__':
    unittest.main()
