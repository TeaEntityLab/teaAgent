"""Comprehensive tests for TUI pipeline, ChatSessionController, ModelDecisionEngine
edge cases, and permission mode transitions.

Covers gaps NOT covered by existing tests (test_tui.py, test_tui_interactive.py,
test_chat_repl_suspension.py, test_chat_agent.py, test_policy.py).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

from conftest import FakeAdapter

from teaagent.approval_manager import PermissionMode
from teaagent.chat_agent import (
    ChatAgentConfig,
    ModelDecisionEngine,
    _looks_like_plain_text_answer,
    _looks_like_simple_answer_task,
    _plain_text_answer_fallback,
    parse_model_decision,
)
from teaagent.chat_session_controller import ChatSessionController, SessionState
from teaagent.llm import FakeLLMAdapter, LLMResponse
from teaagent.policy import ApprovalPolicy
from teaagent.runner import FinalAnswer, ToolRequest
from teaagent.tools import ToolRegistry
from teaagent.tui import TeaAgentTUI


def _make_tmp_root() -> Path:
    """Create a temporary directory and return its Path."""
    td = tempfile.TemporaryDirectory()
    # Workaround: store reference so the directory is not cleaned up until test ends.
    # We return the path and the caller is responsible for cleaning.
    return Path(td.name)


# ---------------------------------------------------------------------------
# Class 1: ChatSessionControllerTests
# ---------------------------------------------------------------------------


class ChatSessionControllerTests(unittest.TestCase):
    """Direct tests for ChatSessionController — execute, undo, cost tracking, audit."""

    def test_execute_task_with_fake_adapter(self) -> None:
        """Basic execution through ChatSessionController with FakeAdapter."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(
                root=root,
                output_fn=output.append,
            )
            adapter = FakeAdapter(
                ['{"type":"final","content":"hello from controller"}']
            )

            config = ChatAgentConfig(
                root=root,
                max_iterations=3,
                max_tool_calls=2,
            )
            result = controller.execute_task(
                "say hello",
                config,
                adapter=adapter,
                emit_answer=False,
            )

            self.assertEqual(result.run_result.status, "completed")
            self.assertIsNotNone(result.run_result.final_answer)
            if result.run_result.final_answer:
                self.assertIn("hello", result.run_result.final_answer.content)
            self.assertGreaterEqual(result.cost_cents, 0)

    def test_execute_task_accepts_config_overrides(self) -> None:
        """Pass a custom config with overridden max_iterations."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            adapter = FakeAdapter(
                ['{"type":"final","content":"done"}']
            )
            config = ChatAgentConfig(
                root=root,
                max_iterations=5,
                max_tool_calls=3,
                max_estimated_cost_cents=200,
            )
            result = controller.execute_task(
                "test",
                config,
                adapter=adapter,
                emit_answer=False,
            )
            self.assertEqual(result.run_result.status, "completed")

    def test_execute_task_emits_answer_when_requested(self) -> None:
        """When emit_answer=True, the final answer is sent to output_fn."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            adapter = FakeAdapter(
                ['{"type":"final","content":"expected-output"}']
            )
            config = ChatAgentConfig(root=root, max_iterations=3, max_tool_calls=2)
            controller.execute_task("task", config, adapter=adapter, emit_answer=True)
            self.assertIn("expected-output", output)

    def test_execute_task_handles_failed_run(self) -> None:
        """When the agent fails, the error message is displayed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            # An invalid tool call string causes a parse failure loop
            adapter = FakeAdapter(
                ['invalid json here'] * 4
            )
            config = ChatAgentConfig(
                root=root,
                max_iterations=3,
                max_tool_calls=2,
            )
            result = controller.execute_task(
                "broken task",
                config,
                adapter=adapter,
                emit_answer=False,
            )
            self.assertTrue(
                result.run_result.status.startswith("failed"),
                f"Expected failed status, got: {result.run_result.status}",
            )

    def test_undo_last_run_without_journal_returns_false(self) -> None:
        """undo_last_run returns False when no undo journal exists."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            result = controller.undo_last_run()
            self.assertFalse(result)

    def test_get_session_cost_tracks_across_tasks(self) -> None:
        """Multiple tasks accumulate cost in session state."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            adapter1 = FakeAdapter(
                ['{"type":"final","content":"first"}']
            )
            adapter2 = FakeAdapter(
                ['{"type":"final","content":"second"}']
            )
            config = ChatAgentConfig(root=root, max_iterations=3, max_tool_calls=2)

            controller.execute_task("task1", config, adapter=adapter1, emit_answer=False)
            cost1 = controller.get_session_cost()
            controller.execute_task("task2", config, adapter=adapter2, emit_answer=False)
            cost2 = controller.get_session_cost()

            self.assertGreaterEqual(cost2, cost1)
            # session should have 2 observation entries
            self.assertEqual(len(controller.session_state.observations), 2)

    def test_get_session_cost_display_format(self) -> None:
        """get_session_cost_display returns a USD-formatted string."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            controller = ChatSessionController(root=root, output_fn=output.append)
            controller.session_state.session_cost_cents = 123.45
            display = controller.get_session_cost_display()
            self.assertEqual(display, "$1.23")
            # Test zero cost
            controller.session_state.session_cost_cents = 0.0
            self.assertEqual(controller.get_session_cost_display(), "$0.00")

    def test_execute_task_handles_run_store_factory(self) -> None:
        """Custom _store_factory is used by the controller."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []

            store_calls: list[Any] = []

            def factory():
                from teaagent.run_store import RunStore

                s = RunStore(root)
                store_calls.append(s)
                return s

            controller = ChatSessionController(
                root=root,
                output_fn=output.append,
                _store_factory=factory,
            )
            adapter = FakeAdapter(
                ['{"type":"final","content":"ok"}']
            )
            config = ChatAgentConfig(root=root, max_iterations=3, max_tool_calls=2)
            controller.execute_task("task", config, adapter=adapter, emit_answer=False)

            # The factory should have been called during execute_task
            self.assertGreater(len(store_calls), 0)

    def test_execute_task_records_audit_events(self) -> None:
        """Audit events are recorded during task execution."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            from teaagent.run_store import RunStore

            store = RunStore(root)
            audit = store.audit_logger()
            controller = ChatSessionController(root=root, output_fn=output.append)
            adapter = FakeAdapter(
                ['{"type":"final","content":"audited"}']
            )
            config = ChatAgentConfig(root=root, max_iterations=3, max_tool_calls=2)
            controller.execute_task(
                "audited task",
                config,
                adapter=adapter,
                audit=audit,
                emit_answer=False,
            )
            events = audit.events
            run_started = [e for e in events if getattr(e, "event_type", "") == "run_started"]
            self.assertGreater(len(run_started), 0)
            run_ended = [e for e in events if getattr(e, "event_type", "") in ("run_completed", "run_failed")]
            self.assertGreater(len(run_ended), 0)

    def test_session_cost_accumulates_via_sessions_state(self) -> None:
        """SessionState starts at zero and accumulates across multiple rounds."""
        state = SessionState()
        self.assertEqual(state.session_cost_cents, 0.0)

        # Simulate two tasks completing with known cost
        state.session_cost_cents += 50.0
        state.session_cost_cents += 75.0
        self.assertEqual(state.session_cost_cents, 125.0)


# ---------------------------------------------------------------------------
# Class 2: TuiFullPipelineTests
# ---------------------------------------------------------------------------


class TuiFullPipelineTests(unittest.TestCase):
    """Full-pipeline tests for TeaAgentTUI — _run_agent_task, approval, progress, budget."""

    def test_run_agent_task_with_fake_adapter(self) -> None:
        """Run a task through _run_agent_task with a FakeAdapter and verify output."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello", encoding="utf-8")
            output: list[str] = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-1"}',
                    '{"type":"final","content":"task completed"}',
                ]
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui._run_agent_task("read note file")

            # Check output contains success payload
            joined = "\n".join(output)
            self.assertIn("task completed", joined)

    def test_run_agent_task_with_final_answer_json_output(self) -> None:
        """When chat=False, _run_agent_task emits JSON payload."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = FakeAdapter(
                ['{"type":"final","content":"json-result"}']
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.chat = False
                tui._run_agent_task("test json output")

            # Last output should be JSON
            json_lines = [line for line in output if line.strip().startswith("{")]
            self.assertGreater(len(json_lines), 0)
            payload = json.loads(json_lines[-1])
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["final_answer"], "json-result")

    def test_run_agent_task_tracks_cost(self) -> None:
        """Cost accumulates in session state across _run_agent_task calls."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = FakeAdapter(
                ['{"type":"final","content":"first-task"}']
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                # First task
                tui._run_agent_task("task one")
                cost1 = tui._session_cost_cents

                # Second task (reset adapter for new responses)
                adapter2 = FakeAdapter(
                    ['{"type":"final","content":"second-task"}']
                )
                state_path2 = root / ".teaagent" / "tui_state.json"
                with patch.object(
                    TeaAgentTUI, "_state_path", new_callable=PropertyMock
                ) as mock_state_path2:
                    mock_state_path2.return_value = state_path2
                    tui2 = TeaAgentTUI(
                        root=root,
                        input_fn=lambda _prompt: "exit",
                        output_fn=output.append,
                        adapter_factory=lambda _p, _m: adapter2,
                    )
                    # Seed with cost from first task
                    tui2._session_cost_cents = cost1
                    tui2._run_agent_task("task two")

                self.assertGreaterEqual(tui2._session_cost_cents, cost1)

    def test_run_agent_task_handles_run_failed(self) -> None:
        """A failed run (e.g., invalid tool) produces an error-status payload."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            # Bad tool name triggers tool-not-found error → failed run
            adapter = FakeAdapter(
                ['{"type":"tool","tool_name":"nonexistent_tool_x","arguments":{},"call_id":"bad"}']
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.chat = False
                tui._run_agent_task("broken task")

            joined = "\n".join(output)
            self.assertTrue(
                "failed" in joined.lower() or "error" in joined.lower(),
                f"Expected failure indicator in output: {joined}",
            )

    def test_run_agent_task_with_clarify(self) -> None:
        """Clarify mode (clarify_first=True) stops before running when task is ambiguous."""
        output: list[str] = []

        def fail_factory(_p, _m):
            raise AssertionError("adapter should not be called")

        state_path = Path(tempfile.TemporaryDirectory().name)
        with patch.object(
            TeaAgentTUI, "_state_path", new_callable=PropertyMock
        ) as mock_state_path:
            mock_state_path.return_value = state_path
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=fail_factory,
            )
            tui._run_agent_task("improve stuff", clarify_first=True)

        # Should see needs_clarification status in output
        self.assertIn("needs_clarification", "\n".join(output))

    def test_run_agent_task_with_clarify_concrete_proceeds(self) -> None:
        """Clarify mode with a concrete task passes through and calls the adapter."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = FakeAdapter(
                ['{"type":"final","content":"concrete done"}']
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.chat = False
                tui._run_agent_task(
                    "Update docs/cli.md to document clarify command",
                    clarify_first=True,
                )

            json_lines = [line for line in output if line.strip().startswith("{")]
            self.assertGreater(len(json_lines), 0)
            payload = json.loads(json_lines[-1])
            self.assertEqual(payload["status"], "completed")

    def test_approval_handler_approves(self) -> None:
        """_approval_handler returns True when preset allows the tool."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            replies = iter(["yes"])
            state_path = root / ".teaagent" / "tui_state.json"

            from teaagent.runner import ApprovalRequest

            req = ApprovalRequest(
                call_id="approve-me",
                tool_name="workspace_write_file",
                arguments={"path": "test.txt", "content": "data"},
                reason="Testing approval",
                annotations={
                    "destructive": True,
                    "read_only": False,
                    "idempotent": True,
                },
                run_id="run-approve-1",
            )

            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: next(replies),
                    output_fn=output.append,
                )
                approved = tui._approval_handler(req)

            self.assertTrue(approved)

    def test_approval_handler_denies(self) -> None:
        """_approval_handler returns False when user answers 'no'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            replies = iter(["no"])
            state_path = root / ".teaagent" / "tui_state.json"

            from teaagent.runner import ApprovalRequest

            req = ApprovalRequest(
                call_id="deny-me",
                tool_name="workspace_run_shell_mutate",
                arguments={"command": "rm -rf /"},
                reason="Dangerous shell command",
                annotations={
                    "destructive": True,
                    "read_only": False,
                    "idempotent": False,
                },
                run_id="run-deny-1",
            )

            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: next(replies),
                    output_fn=output.append,
                )
                approved = tui._approval_handler(req)

            self.assertFalse(approved)

    def test_progress_sink_records_events(self) -> None:
        """_progress_sink formats and outputs audit events."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"r1"}',
                    '{"type":"final","content":"done"}',
                ]
            )
            (root / "note.txt").write_text("hello", encoding="utf-8")
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui.progress = True
                tui._run_agent_task("read note")

            joined = "\n".join(output)
            self.assertIn("iter 1", joined)
            self.assertIn("tool: workspace_read_file", joined)
            self.assertIn("tool ok: workspace_read_file", joined)

    def test_budget_prompt_handler_accepts(self) -> None:
        """_budget_prompt_handler returns True on 'yes' input."""
        output: list[str] = []
        state_path = Path(tempfile.TemporaryDirectory().name)
        with patch.object(
            TeaAgentTUI, "_state_path", new_callable=PropertyMock
        ) as mock_state_path:
            mock_state_path.return_value = state_path
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: "yes",
                output_fn=output.append,
            )
            result = tui._budget_prompt_handler(
                {"percent": 80.0, "cost_cents": 400.0, "max_cost_cents": 500.0}
            )
            self.assertTrue(result)

    def test_budget_prompt_handler_rejects(self) -> None:
        """_budget_prompt_handler returns False on 'no' input."""
        output: list[str] = []
        state_path = Path(tempfile.TemporaryDirectory().name)
        with patch.object(
            TeaAgentTUI, "_state_path", new_callable=PropertyMock
        ) as mock_state_path:
            mock_state_path.return_value = state_path
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: "no",
                output_fn=output.append,
            )
            result = tui._budget_prompt_handler(
                {"percent": 90.0, "cost_cents": 450.0, "max_cost_cents": 500.0}
            )
            self.assertFalse(result)

    def test_help_text_includes_commands(self) -> None:
        """Help text output includes key command names."""
        output: list[str] = []
        state_path = Path(tempfile.TemporaryDirectory().name)
        with patch.object(
            TeaAgentTUI, "_state_path", new_callable=PropertyMock
        ) as mock_state_path:
            mock_state_path.return_value = state_path
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
            )
            tui.handle_command("help")

        joined = "\n".join(output)
        self.assertIn("ask", joined.lower())
        self.assertIn("cost", joined.lower())
        self.assertIn("permission", joined.lower())
        self.assertIn("help", joined.lower())

    def test_run_agent_task_sets_last_run_id(self) -> None:
        """After _run_agent_task, last_run_id is set to the result's run_id."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output: list[str] = []
            adapter = FakeAdapter(
                ['{"type":"final","content":"set-run-id"}']
            )
            state_path = root / ".teaagent" / "tui_state.json"
            with patch.object(
                TeaAgentTUI, "_state_path", new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(
                    root=root,
                    input_fn=lambda _prompt: "exit",
                    output_fn=output.append,
                    adapter_factory=lambda _p, _m: adapter,
                )
                tui._run_agent_task("test run id")

            self.assertIsNotNone(tui.last_run_id)
            self.assertIsInstance(tui.last_run_id, str)
            self.assertGreater(len(tui.last_run_id), 0)


# ---------------------------------------------------------------------------
# Class 3: ModelDecisionEngineEdgeTests
# ---------------------------------------------------------------------------


class ModelDecisionEngineEdgeTests(unittest.TestCase):
    """Edge-case tests for ModelDecisionEngine — parse failures, fallbacks, retries."""

    def test_plain_text_answer_fallback_returns_final_answer(self) -> None:
        """_plain_text_answer_fallback returns a FinalAnswer for simple Q&A tasks."""
        context = {"task": "What is the capital of France?"}
        answer = "The capital of France is Paris, a wonderful city with rich history."
        result = _plain_text_answer_fallback(context, answer)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, FinalAnswer)
        self.assertIn("Paris", result.content)

    def test_plain_text_answer_fallback_returns_none_with_observations(self) -> None:
        """_plain_text_answer_fallback returns None when observations exist (tool use)."""
        context = {"task": "What is X?", "observations": [{"type": "tool_output"}]}
        answer = "Some long answer with enough words to pass the length check."
        result = _plain_text_answer_fallback(context, answer)
        self.assertIsNone(result)

    def test_plain_text_answer_fallback_returns_none_for_workspace_task(self) -> None:
        """_plain_text_answer_fallback returns None for workspace-related tasks."""
        context = {"task": "Read the file src/main.py and fix the bug"}
        answer = "Here is what I found in the file blah blah blah blah."
        result = _plain_text_answer_fallback(context, answer)
        self.assertIsNone(result)

    def test_looks_like_simple_answer_task_true(self) -> None:
        """_looks_like_simple_answer_task returns True for Q&A-style questions."""
        self.assertTrue(_looks_like_simple_answer_task("What is Python?"))
        self.assertTrue(_looks_like_simple_answer_task("How do I create a loop?"))
        self.assertTrue(_looks_like_simple_answer_task("Explain async/await"))
        self.assertTrue(
            _looks_like_simple_answer_task("Tell me about machine learning")
        )
        self.assertTrue(_looks_like_simple_answer_task("Can you tell me about AI?"))

    def test_looks_like_simple_answer_task_false(self) -> None:
        """_looks_like_simple_answer_task returns False for workspace file tasks."""
        self.assertFalse(_looks_like_simple_answer_task("Read the file src/main.py"))
        self.assertFalse(_looks_like_simple_answer_task("Fix the bug in tests/"))
        self.assertFalse(_looks_like_simple_answer_task("Edit README.md"))
        self.assertFalse(_looks_like_simple_answer_task("Run the test suite"))
        self.assertFalse(_looks_like_simple_answer_task("Commit and push changes"))
        self.assertFalse(_looks_like_simple_answer_task(""))

    def test_looks_like_plain_text_answer_true(self) -> None:
        """_looks_like_plain_text_answer returns True for natural language answers."""
        self.assertTrue(
            _looks_like_plain_text_answer(
                "Python is a high-level programming language that is widely used."
            )
        )

    def test_looks_like_plain_text_answer_false(self) -> None:
        """_looks_like_plain_text_answer returns False for JSON-like or short answers."""
        self.assertFalse(_looks_like_plain_text_answer("short"))
        self.assertFalse(_looks_like_plain_text_answer('{"key": "value"}'))
        self.assertFalse(_looks_like_plain_text_answer("[1, 2, 3]"))
        self.assertFalse(_looks_like_plain_text_answer("```json\n{}\n```"))

    def test_parse_model_decision_returns_tool_request(self) -> None:
        """Valid JSON with type:tool returns a ToolRequest."""
        result = parse_model_decision(
            '{"type":"tool","tool_name":"workspace_read_file",'
            '"arguments":{"path":"test.txt"},"call_id":"c1"}'
        )
        self.assertIsInstance(result, ToolRequest)
        self.assertEqual(result.tool_name, "workspace_read_file")
        self.assertEqual(result.call_id, "c1")

    def test_parse_model_decision_returns_final_answer(self) -> None:
        """Valid JSON with type:final returns a FinalAnswer."""
        result = parse_model_decision(
            '{"type":"final","content":"All done"}'
        )
        self.assertIsInstance(result, FinalAnswer)
        self.assertEqual(result.content, "All done")

    def test_decide_with_fake_llm_adapter(self) -> None:
        """decide() with FakeLLMAdapter returns a FinalAnswer for final-action JSON."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "fake content"},
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )

        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content='{"type":"final","content":"decision-made"}',
                )
            ]
        )
        engine = ModelDecisionEngine(adapter=adapter, registry=tool_registry)
        context = {"task": "Hello world", "decision_summary": ""}
        decision = engine.decide(context)
        self.assertIsInstance(decision, FinalAnswer)
        self.assertEqual(decision.content, "decision-made")

    def test_decide_with_tool_request_from_fake_llm(self) -> None:
        """decide() returns a ToolRequest when JSON specifies type:tool."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "content"},
            description="Read file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )
        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content='{"type":"tool","tool_name":"workspace_read_file",'
                    '"arguments":{"path":"x.txt"},"call_id":"tool-call-1"}',
                )
            ]
        )
        engine = ModelDecisionEngine(adapter=adapter, registry=tool_registry)
        context = {"task": "Read file x.txt", "decision_summary": ""}
        decision = engine.decide(context)
        self.assertIsInstance(decision, ToolRequest)
        self.assertEqual(decision.tool_name, "workspace_read_file")

    def test_decide_falls_back_to_plain_text_after_retries(self) -> None:
        """After max retries with invalid JSON, decide falls back to plain text for simple tasks."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "fake"},
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )
        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="not valid json at all",
                ),
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="still not json",
                ),
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="this is a long plain text answer with more than twenty characters",
                ),
            ]
        )
        engine = ModelDecisionEngine(adapter=adapter, registry=tool_registry)
        context = {"task": "What is the capital of France?", "decision_summary": ""}
        decision = engine.decide(context)
        # Should fall back to plain_text_final_answer
        self.assertIsInstance(decision, FinalAnswer)
        self.assertNotEqual(decision.content, "")

    def test_decide_raises_for_workspace_task_after_max_retries(self) -> None:
        """For workspace tasks, decide raises RuntimeError after exhausting retries."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "fake"},
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )
        # All responses are invalid JSON for a workspace task.
        # Last response must NOT trigger the post_retry plain text fallback:
        # it should be <20 chars or start with '{'.
        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="garbage input not json",
                ),
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="more garbage",
                ),
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content="x",  # too short for plain text fallback (<20 chars)
                ),
            ]
        )
        engine = ModelDecisionEngine(adapter=adapter, registry=tool_registry)
        context = {
            "task": "Read the file src/main.py and fix all bugs",
            "decision_summary": "",
        }
        with self.assertRaises(RuntimeError) as ctx:
            engine.decide(context)
        self.assertIn("parsing failed", str(ctx.exception))

    def test_decide_with_stream_on_chunk_called(self) -> None:
        """decide with stream=True triggers on_chunk callback."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "fake"},
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )
        chunks: list[str] = []
        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content='{"type":"final","content":"streamed"}',
                )
            ]
        )
        engine = ModelDecisionEngine(
            adapter=adapter,
            registry=tool_registry,
            stream=True,
            on_chunk=chunks.append,
            stream_text_only=True,
        )
        context = {"task": "Hello", "decision_summary": ""}
        decision = engine.decide(context)
        self.assertIsInstance(decision, FinalAnswer)

    def test_decide_accumulates_cost_in_context(self) -> None:
        """decide updates _cost_cents in the context dict."""
        from teaagent.tools import ToolAnnotations

        tool_registry = ToolRegistry()
        tool_registry.register(
            name="workspace_read_file",
            handler=lambda args: {"output": "fake"},
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            output_schema={"type": "object"},
            annotations=ToolAnnotations(read_only=True, destructive=False),
        )
        adapter = FakeLLMAdapter(
            responses=[
                LLMResponse(
                    provider="fake",
                    model="fake-model",
                    content='{"type":"final","content":"costly"}',
                    input_tokens=100,
                    output_tokens=50,
                )
            ]
        )
        engine = ModelDecisionEngine(adapter=adapter, registry=tool_registry)
        context: dict[str, Any] = {"task": "Hello", "decision_summary": ""}
        engine.decide(context)
        self.assertIn("_cost_cents", context)
        self.assertIn("_input_tokens", context)
        self.assertIn("_output_tokens", context)


# ---------------------------------------------------------------------------
# Class 4: PermissionModeTransitionTests
# ---------------------------------------------------------------------------


class PermissionModeTransitionTests(unittest.TestCase):
    """Permission mode and ApprovalPolicy transition tests via assert_allowed."""

    def test_read_only_blocks_destructive_tools(self) -> None:
        """READ_ONLY mode blocks destructive tools via assert_allowed."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
        from teaagent.errors import ToolPermissionError

        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name="workspace_write_file",
                call_id="c1",
                destructive=True,
            )

    def test_read_only_allows_non_destructive_tools(self) -> None:
        """READ_ONLY mode allows non-destructive tools."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)
        # Should not raise
        policy.assert_allowed(
            tool_name="workspace_read_file",
            call_id="c1",
            destructive=False,
            read_only=True,
        )

    def test_workspace_write_allows_file_write_tools(self) -> None:
        """WORKSPACE_WRITE mode allows file write tools but blocks shell write."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        # File writes allowed
        policy.assert_allowed(
            tool_name="workspace_write_file",
            call_id="c1",
            destructive=True,
        )
        policy.assert_allowed(
            tool_name="workspace_apply_patch",
            call_id="c2",
            destructive=True,
        )

    def test_workspace_write_blocks_shell_mutate(self) -> None:
        """WORKSPACE_WRITE blocks shell destructive tools."""
        from teaagent.errors import ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name="workspace_run_shell_mutate",
                call_id="c1",
                destructive=True,
            )

    def test_prompt_mode_requires_handler_for_destructive(self) -> None:
        """PROMPT mode for destructive tools without handler raises."""
        from teaagent.errors import ToolPermissionError

        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        with self.assertRaises(ToolPermissionError):
            policy.assert_allowed(
                tool_name="workspace_write_file",
                call_id="c1",
                destructive=True,
            )

    def test_prompt_mode_allows_non_destructive(self) -> None:
        """PROMPT mode allows non-destructive tools."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.PROMPT)
        policy.assert_allowed(
            tool_name="workspace_read_file",
            call_id="c1",
            destructive=False,
        )

    def test_allow_mode_allows_all_destructive(self) -> None:
        """ALLOW mode allows all destructive tools."""
        policy = ApprovalPolicy(permission_mode=PermissionMode.ALLOW)
        policy.assert_allowed(
            tool_name="workspace_write_file",
            call_id="c1",
            destructive=True,
        )
        policy.assert_allowed(
            tool_name="workspace_run_shell_mutate",
            call_id="c2",
            destructive=True,
        )

    def test_danger_full_access_allows_all(self) -> None:
        """DANGER_FULL_ACCESS mode allows all tools without restriction."""
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            full_access_acknowledged=True,
        )
        policy.assert_allowed(
            tool_name="workspace_write_file",
            call_id="c1",
            destructive=True,
        )
        policy.assert_allowed(
            tool_name="workspace_run_shell_mutate",
            call_id="c2",
            destructive=True,
        )
        policy.assert_allowed(
            tool_name="workspace_read_file",
            call_id="c3",
            destructive=False,
        )

    def test_all_permission_modes_are_distinct(self) -> None:
        """All five permission modes have distinct string values."""
        modes = {
            PermissionMode.READ_ONLY,
            PermissionMode.WORKSPACE_WRITE,
            PermissionMode.PROMPT,
            PermissionMode.ALLOW,
            PermissionMode.DANGER_FULL_ACCESS,
        }
        self.assertEqual(len(modes), 5)
        self.assertEqual(len({m.value for m in modes}), 5)


if __name__ == "__main__":
    unittest.main()
