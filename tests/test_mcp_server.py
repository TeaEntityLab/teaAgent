from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from teaagent import handle_mcp_request, serve_mcp_stdio
from teaagent.workspace_tools import build_workspace_tool_registry


class MCPServerTests(unittest.TestCase):
    def test_initialize_returns_protocol_and_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            response = handle_mcp_request(registry, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})

            self.assertEqual(response["id"], 1)
            self.assertIn("protocolVersion", response["result"])
            self.assertEqual(response["result"]["serverInfo"]["name"], "teaagent")

    def test_tools_list_returns_workspace_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            response = handle_mcp_request(registry, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

            tools = response["result"]["tools"]
            names = {tool["name"] for tool in tools}
            self.assertIn("workspace_read_file", names)
            self.assertIn("inputSchema", tools[0])

    def test_tools_call_executes_read_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hello.txt").write_text("hi", encoding="utf-8")
            registry = build_workspace_tool_registry(tmp)

            response = handle_mcp_request(
                registry,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "workspace_read_file", "arguments": {"path": "hello.txt"}},
                },
            )

            payload = response["result"]
            self.assertFalse(payload["isError"])
            text = json.loads(payload["content"][0]["text"])
            self.assertEqual(text["content"], "hi")

    def test_tools_call_returns_is_error_for_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            response = handle_mcp_request(
                registry,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "workspace_read_file", "arguments": {}},
                },
            )

            self.assertTrue(response["result"]["isError"])

    def test_unknown_method_returns_method_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_workspace_tool_registry(tmp)

            response = handle_mcp_request(registry, {"jsonrpc": "2.0", "id": 5, "method": "ping"})

            self.assertEqual(response["error"]["code"], -32601)

    def test_serve_mcp_stdio_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "hello.txt").write_text("hi", encoding="utf-8")
            registry = build_workspace_tool_registry(tmp)
            stdin = io.StringIO(
                "\n".join(
                    [
                        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/call",
                                "params": {"name": "workspace_read_file", "arguments": {"path": "hello.txt"}},
                            }
                        ),
                        "",
                    ]
                )
            )
            stdout = io.StringIO()

            exit_code = serve_mcp_stdio(registry, stdin=stdin, stdout=stdout)

            lines = [line for line in stdout.getvalue().splitlines() if line]
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(lines), 2)
            init_response = json.loads(lines[0])
            call_response = json.loads(lines[1])
            self.assertEqual(init_response["id"], 1)
            self.assertFalse(call_response["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
