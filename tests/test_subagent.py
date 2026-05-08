from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent import ChatAgentConfig, run_chat_agent
from teaagent.cli import main


class SubagentTests(unittest.TestCase):
    def test_subagent_tool_executes_child_run_and_returns_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"subagent","arguments":{"task":"child task"},"call_id":"sub-1"}',
                    '{"type":"final","content":"child done"}',
                    '{"type":"final","content":"parent done"}',
                ]
            )

            result = run_chat_agent(
                task="parent task",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp, enable_subagent=True),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.final_answer.content, "parent done")

    def test_subagent_depth_limit_blocks_second_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"subagent","arguments":{"task":"level1"},"call_id":"sub-1"}',
                    '{"type":"tool","tool_name":"subagent","arguments":{"task":"level2"},"call_id":"sub-2"}',
                    '{"type":"final","content":"level1 done"}',
                    '{"type":"final","content":"parent done"}',
                ]
            )

            result = run_chat_agent(
                task="parent",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp, enable_subagent=True, max_subagent_depth=1),
            )

            self.assertEqual(result.status, "completed")

    def test_subagent_tool_absent_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"subagent","arguments":{"task":"child"},"call_id":"sub-1"}'
                ]
            )

            result = run_chat_agent(
                task="parent",
                adapter=adapter,
                config=ChatAgentConfig.from_root(tmp),
            )

            self.assertNotEqual(result.status, "completed")

    def test_cli_agent_run_subagent_flag_exposes_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"subagent","arguments":{"task":"child"},"call_id":"sub-1"}',
                    '{"type":"final","content":"child"}',
                    '{"type":"final","content":"parent"}',
                ]
            )

            with patch("teaagent.cli.create_llm_adapter", return_value=adapter), redirect_stdout(output):
                exit_code = main(["agent", "run", "gpt", "delegate work", "--subagent", "--root", tmp])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "completed")


if __name__ == "__main__":
    unittest.main()
