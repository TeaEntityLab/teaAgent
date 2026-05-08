from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent import (
    ApprovalPolicy,
    ChatAgentConfig,
    MemoryCatalog,
    PermissionMode,
    parse_model_decision,
    run_chat_agent,
)
from teaagent.cli import main
from teaagent.errors import ToolPermissionError
from teaagent.runner import ToolRequest


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

    def test_chat_agent_injects_task_spec_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(['{"type":"final","content":"done"}'])

            result = run_chat_agent(
                task="Update docs",
                task_spec="Clarified task specification:\nTASK: Update docs",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp),
            )

            self.assertEqual(result.status, "completed")
            self.assertIn("Clarified task specification", adapter.requests[0].messages[0].content)

    def test_chat_agent_injects_matching_memories_into_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            MemoryCatalog(tmp).add("docs cli clarify command should mention ambiguity gate")
            adapter = FakeAdapter(['{"type":"final","content":"done"}'])

            result = run_chat_agent(
                task="docs cli clarify",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp),
            )

            self.assertEqual(result.status, "completed")
            self.assertIn("ambiguity gate", adapter.requests[0].messages[0].content)

    def test_destructive_decision_is_blocked_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
                ]
            )

            result = run_chat_agent(task="write", adapter=adapter, config=ChatAgentConfig.from_root(tmp))

            self.assertEqual(result.status, "pending_approval")
            self.assertEqual(result.metadata["approval"]["call_id"], "write-1")

    def test_destructive_decision_can_be_approved_by_hitl_handler(self) -> None:
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
                config=ChatAgentConfig.from_root(tmp, approval_handler=lambda _request: True),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual((Path(tmp) / "x.txt").read_text(encoding="utf-8"), "x")

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

    def test_destructive_decision_can_be_approved_by_call_id(self) -> None:
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
                config=ChatAgentConfig.from_root(tmp, approved_call_ids=frozenset({"write-1"})),
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
        with self.assertRaises(ToolPermissionError):
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

    def test_cli_agent_run_route_model_uses_routed_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            adapter = FakeAdapter(['{"type":"final","content":"reviewed"}'])

            with patch("teaagent.cli.create_llm_adapter", return_value=adapter) as create_adapter, redirect_stdout(output):
                exit_code = main(["agent", "run", "gpt", "review this patch", "--route-model", "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            create_adapter.assert_called_once_with("gpt", model="gpt-4o")
            self.assertEqual(payload["routing"]["category"], "review")
            self.assertEqual(payload["final_answer"], "reviewed")

    def test_cli_agent_run_approve_call_id_allows_exact_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )

            with patch("teaagent.cli.create_llm_adapter", return_value=adapter), redirect_stdout(output):
                exit_code = main(["agent", "run", "gpt", "write", "--root", tmp, "--approve-call-id", "write-1"])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual((Path(tmp) / "x.txt").read_text(encoding="utf-8"), "x")

    def test_cli_agent_run_returns_pending_approval_for_unapproved_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}'
                ]
            )

            with patch("teaagent.cli.create_llm_adapter", return_value=adapter), redirect_stdout(output):
                exit_code = main(["agent", "run", "gpt", "write", "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["status"], "pending_approval")
            self.assertEqual(payload["approval"]["call_id"], "write-1")

    def test_cli_agent_run_hitl_approval_continues_same_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )

            with (
                patch("teaagent.cli.create_llm_adapter", return_value=adapter),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                exit_code = main(["agent", "run", "gpt", "write", "--root", tmp, "--hitl-approval"])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual((Path(tmp) / "x.txt").read_text(encoding="utf-8"), "x")

    def test_cli_agent_resume_replays_original_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_adapter = FakeAdapter(['{"type":"final","content":"first"}'])
            with patch("teaagent.cli.create_llm_adapter", return_value=first_adapter), redirect_stdout(io.StringIO()) as first_out:
                self.assertEqual(main(["agent", "run", "gpt", "summarize repo", "--root", tmp]), 0)
            run_id = json.loads(first_out.getvalue())["run_id"]

            resume_adapter = FakeAdapter(['{"type":"final","content":"second"}'])
            with patch("teaagent.cli.create_llm_adapter", return_value=resume_adapter), redirect_stdout(io.StringIO()) as resume_out:
                exit_code = main(["agent", "resume", "gpt", run_id, "--root", tmp])

            payload = json.loads(resume_out.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["resumed_from"], run_id)
            self.assertEqual(payload["task"], "summarize repo")
            self.assertEqual(payload["final_answer"], "second")

    def test_cli_agent_resume_unknown_run_id_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["agent", "resume", "gpt", "missing", "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["status"], "error")


if __name__ == "__main__":
    unittest.main()
