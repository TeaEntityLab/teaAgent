from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from conftest import FakeAdapter

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.mcp_http import MCP_PATH, SESSION_HEADER, build_mcp_http_server
from teaagent.run_store import RunStore
from teaagent.workspace_tools import build_workspace_tool_registry


class EndToEndTests(unittest.TestCase):
    def test_agent_loop_persists_audit_and_workspace_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello', encoding='utf-8')
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"hello.txt"},"call_id":"read-1"}',
                    '{"type":"final","content":"done"}',
                ]
            )
            store = RunStore(root)
            audit = store.audit_logger()

            result = run_chat_agent(
                task='read hello',
                adapter=adapter,
                config=ChatAgentConfig.from_root(root, max_iterations=3, max_tool_calls=2),
                audit=audit,
            )
            store.logger_for_result(result, audit)

            events = store.show_run(result.run_id)
            event_types = [event['event_type'] for event in events]
            self.assertEqual(result.status, 'completed')
            self.assertIn('tool_call_completed', event_types)
            self.assertIn('run_completed', event_types)

    def test_pending_approval_can_resume_with_recorded_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"out.txt","content":"ok"},"call_id":"write-1"}',
                ]
            )
            store = RunStore(root)
            audit = store.audit_logger()

            result = run_chat_agent(
                task='write file',
                adapter=adapter,
                config=ChatAgentConfig.from_root(root, max_iterations=2, max_tool_calls=1),
                audit=audit,
            )
            store.logger_for_result(result, audit)

            resumed = run_chat_agent(
                task='write file',
                adapter=FakeAdapter(['{"type":"final","content":"resumed"}']),
                config=ChatAgentConfig.from_root(
                    root,
                    approved_call_ids=frozenset({'write-1'}),
                    max_iterations=2,
                    max_tool_calls=2,
                ),
                initial_observations=store.observations_for_run(result.run_id),
            )

            self.assertEqual(result.status, 'pending_approval')
            self.assertEqual(resumed.status, 'completed')

    def test_mcp_http_initialize_and_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hello.txt').write_text('hello', encoding='utf-8')
            server, _sessions = build_mcp_http_server(
                build_workspace_tool_registry(root), host='127.0.0.1', port=0
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                session_id = self._initialize(host, port)
                body = json.dumps(
                    {
                        'jsonrpc': '2.0',
                        'id': 2,
                        'method': 'tools/call',
                        'params': {
                            'name': 'workspace_read_file',
                            'arguments': {'path': 'hello.txt'},
                        },
                    }
                ).encode('utf-8')
                status, data = self._request(
                    host,
                    port,
                    body,
                    headers={SESSION_HEADER: session_id},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            payload = json.loads(data)
            self.assertEqual(status, 200)
            self.assertFalse(payload['result']['isError'])

    def _initialize(self, host: str, port: int) -> str:
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}).encode(
            'utf-8'
        )
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.request(
                'POST',
                MCP_PATH,
                body=body,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            response = conn.getresponse()
            response.read()
            return dict(response.getheaders())[SESSION_HEADER]
        finally:
            conn.close()

    def _request(
        self, host: str, port: int, body: bytes, *, headers: dict[str, str]
    ) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            all_headers = {
                'Content-Type': 'application/json',
                'Content-Length': str(len(body)),
                **headers,
            }
            conn.request('POST', MCP_PATH, body=body, headers=all_headers)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
