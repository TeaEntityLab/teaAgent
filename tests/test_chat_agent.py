from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from teaagent import (
    ApprovalPolicy,
    AuditLogger,
    ChatAgentConfig,
    LLMResponse,
    PermissionMode,
    ToolAnnotations,
    ToolRegistry,
    parse_model_decision,
    run_chat_agent,
)
from teaagent.cli import main
from teaagent.runner import ToolRequest
from teaagent.workspace_tools import build_workspace_tool_registry


class FakeAdapter:
    provider = "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return LLMResponse(provider="fake", model="fake-model", content=self.outputs.pop(0))


class ChatAgentTests(unittest.TestCase):
    def test_parse_model_decision_accepts_tool_and_final(self) -> None:
        tool = parse_model_decision('{"type":"tool","tool_name":"x","arguments":{"a":1},"call_id":"c1"}')
        final = parse_model_decision('```json\n{"type":"final","content":"done"}\n```')

        self.assertIsInstance(tool, ToolRequest)
        self.assertEqual(tool.call_id, "c1")
        self.assertEqual(final.content, "done")

    def test_chat_agent_runs_tool_then_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hello.txt").write_text("hello", encoding="utf-8")
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"hello.txt"},"call_id":"read-1"}',
                    '{"type":"final","content":"read hello.txt"}',
                ]
            )

            result = run_chat_agent(
                task="read hello",
                adapter=adapter,
                config=ChatAgentConfig.from_root(root, max_iterations=3, max_tool_calls=2),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.tool_calls, 1)
            self.assertEqual(result.final_answer.content, "read hello.txt")
            self.assertIn("workspace_read_file", adapter.requests[0].system)

    def test_destructive_decision_is_blocked_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
                ]
            )

            result = run_chat_agent(task="write", adapter=adapter, config=ChatAgentConfig.from_root(tmp))

            self.assertEqual(result.status, "failed:permission")

    def test_destructive_decision_can_be_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )

            result = run_chat_agent(
                task="write",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp, allow_destructive=True),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual((Path(tmp) / "x.txt").read_text(encoding="utf-8"), "x")

    def test_workspace_write_permission_allows_file_write_not_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )
            shell_adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"touch y.txt"},"call_id":"shell-1"}'
                ]
            )

            write_result = run_chat_agent(
                task="write",
                adapter=write_adapter,
                config=ChatAgentConfig.from_root(tmp, permission_mode=PermissionMode.WORKSPACE_WRITE),
            )
            shell_result = run_chat_agent(
                task="shell",
                adapter=shell_adapter,
                config=ChatAgentConfig.from_root(tmp, permission_mode=PermissionMode.WORKSPACE_WRITE),
            )

            self.assertEqual(write_result.status, "completed")
            self.assertEqual(shell_result.status, "failed:permission")

    def test_approval_policy_allow_all_destructive(self) -> None:
        ApprovalPolicy(allow_all_destructive=True).assert_allowed(
            tool_name="workspace_write_file",
            call_id="any",
            destructive=True,
        )

    def test_read_only_permission_blocks_destructive(self) -> None:
        with self.assertRaises(Exception):
            ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY).assert_allowed(
                tool_name="workspace_write_file",
                call_id="any",
                destructive=True,
            )

    def test_cli_agent_help(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["agent", "run", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Run one autonomous task", output.getvalue())


if __name__ == "__main__":
    unittest.main()
