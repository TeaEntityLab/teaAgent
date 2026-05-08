from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from teaagent import LLMResponse
from teaagent.cli import main
from teaagent.tui import TeaAgentTUI


class FakeAdapter:
    provider = "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)

    def complete(self, _request):
        return LLMResponse(provider="fake", model="fake", content=self.outputs.pop(0))


class CapturingAdapterFactory:
    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = []

    def __call__(self, provider, model):
        self.calls.append((provider, model))
        return self.adapter


class TUITests(unittest.TestCase):
    def test_tui_handles_doctor_smoke_query_and_exit(self) -> None:
        commands = iter([
            "doctor",
            "smoke",
            "query MATCH (n:SmokeTest) RETURN n.name",
            "exit",
        ])
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: next(commands), output_fn=output.append)

        exit_code = tui.run()

        self.assertEqual(exit_code, 0)
        self.assertEqual(output[0], "TeaAgent TUI 0.1.0")
        doctor_payload = json.loads(output[2])
        self.assertTrue(doctor_payload["ok"])
        self.assertEqual(json.loads(output[3]), [{"n.name": "TeaAgent"}])
        self.assertEqual(json.loads(output[4]), [{"n.name": "TeaAgent"}])
        self.assertEqual(output[-1], "bye")

    def test_tui_use_switches_database_label(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("use ./graph.db"))

        self.assertEqual(tui.database, "./graph.db")
        self.assertEqual(output, ["database: ./graph.db"])

    def test_tui_agent_settings_and_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello", encoding="utf-8")
            commands = iter([
                f"root {root}",
                "provider gpt",
                "model test-model",
                "permission workspace-write",
                "ask read note",
                "runs",
                "exit",
            ])
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-note"}',
                    '{"type":"final","content":"note read"}',
                ]
            )
            tui = TeaAgentTUI(
                input_fn=lambda _prompt: next(commands),
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            exit_code = tui.run()

            self.assertEqual(exit_code, 0)
            self.assertIn(f"root: {root.resolve()}", output)
            self.assertIn("provider: gpt", output)
            self.assertIn("model: test-model", output)
            self.assertIn("permission: workspace-write", output)
            agent_payload = json.loads(output[-2])
            if isinstance(agent_payload, list):
                agent_payload = json.loads(output[-3])
            self.assertEqual(agent_payload["status"], "completed")
            self.assertEqual(agent_payload["final_answer"], "note read")
            runs_payload = json.loads(output[-2])
            self.assertEqual(runs_payload[0]["status"], "completed")

    def test_tui_destructive_toggle(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("destructive on"))
        self.assertTrue(tui.allow_destructive)
        self.assertEqual(output, ["destructive: on"])

    def test_tui_permission_mode(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("permission read-only"))

        self.assertEqual(tui.permission_mode.value, "read-only")
        self.assertEqual(output, ["permission: read-only"])

    def test_tui_approval_commands(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("approve write-1"))
        self.assertTrue(tui.handle_command("approvals"))
        self.assertTrue(tui.handle_command("unapprove write-1"))
        self.assertTrue(tui.handle_command("approvals"))

        self.assertEqual(output[0], "approved: write-1")
        self.assertEqual(json.loads(output[1]), ["write-1"])
        self.assertEqual(output[2], "unapproved: write-1")
        self.assertEqual(json.loads(output[3]), [])

    def test_tui_approved_call_id_allows_exact_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"x.txt","content":"x"},"call_id":"write-1"}',
                    '{"type":"final","content":"wrote"}',
                ]
            )
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append, adapter_factory=lambda _provider, _model: adapter)

            self.assertTrue(tui.handle_command("approve write-1"))
            self.assertTrue(tui.handle_command("ask write file"))

            payload = json.loads(output[-1])
            self.assertEqual(payload["status"], "completed")
            self.assertEqual((Path(tmp) / "x.txt").read_text(encoding="utf-8"), "x")

    def test_tui_clarify_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("clarify improve stuff"))

        payload = json.loads(output[0])
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["question"], "What action do you want TeaAgent to take?")

    def test_tui_progress_streams_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello", encoding="utf-8")
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"r1"}',
                    '{"type":"final","content":"done"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command("progress on"))
            self.assertTrue(tui.handle_command("ask read note"))

            joined = "\n".join(output)
            self.assertIn("iter 1", joined)
            self.assertIn("tool: workspace_read_file", joined)
            self.assertIn("tool ok: workspace_read_file", joined)

    def test_tui_resume_replays_persisted_run_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"final","content":"first"}',
                    '{"type":"final","content":"second"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command("ask read note"))
            run_id = json.loads(output[-1])["run_id"]
            self.assertTrue(tui.handle_command(f"resume {run_id}"))

            resume_payload = json.loads(output[-1])
            self.assertEqual(resume_payload["final_answer"], "second")
            self.assertIn(f"resume: {run_id}", output)

    def test_tui_preflight_command_uses_current_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append)
            self.assertTrue(tui.handle_command("route-model on"))
            self.assertTrue(tui.handle_command("preflight review this patch for regressions in the test suite"))

            payload = json.loads(output[-1])
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["routing"]["category"], "review")
            self.assertEqual(payload["model"], "gpt-4o")

    def test_tui_memory_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append)

            self.assertTrue(tui.handle_command("memory add Prefer read-only mode for audits"))
            memory_id = json.loads(output[0])["memory_id"]
            self.assertTrue(tui.handle_command("memory search audits"))
            self.assertTrue(tui.handle_command(f"memory show {memory_id}"))

            self.assertEqual(json.loads(output[1])[0]["memory_id"], memory_id)
            self.assertEqual(json.loads(output[2])["content"], "Prefer read-only mode for audits")

    def test_tui_route_model_preview_and_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"reviewed"}'])
            factory = CapturingAdapterFactory(adapter)
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append, adapter_factory=factory)

            self.assertTrue(tui.handle_command("route-model on"))
            self.assertTrue(tui.handle_command("route review this patch"))
            self.assertTrue(tui.handle_command("ask review this patch"))

            route_payload = json.loads(output[1])
            ask_payload = json.loads(output[-1])
            self.assertEqual(route_payload["model"], "gpt-4o")
            self.assertEqual(factory.calls[0], ("gpt", "gpt-4o"))
            self.assertEqual(ask_payload["routing"]["category"], "review")

    def test_tui_ask_clarify_stops_before_adapter_when_ambiguous(self) -> None:
        output = []

        def fail_factory(_provider, _model):
            raise AssertionError("adapter should not be created")

        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append, adapter_factory=fail_factory)

        self.assertTrue(tui.handle_command("ask --clarify improve stuff"))

        payload = json.loads(output[0])
        self.assertEqual(payload["status"], "needs_clarification")
        self.assertTrue(payload["clarification"]["needs_clarification"])

    def test_cli_tui_help_in_parser(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["tui", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Start an interactive terminal UI", output.getvalue())
        self.assertIn("--provider", output.getvalue())

    def test_tui_empty_command_continues(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command(""))

    def test_tui_help_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("help"))
        self.assertIn("help", output[0])
        self.assertIn("provider", output[0])
        self.assertIn("ask", output[0])

    def test_tui_unknown_command(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("unknown-cmd"))
        self.assertIn("unknown command", output[0])

    def test_tui_malformed_shlex_input(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command('unclosed "quote'))

    def test_tui_provider_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("provider"))
        self.assertIn("requires exactly one", output[0])
        self.assertTrue(tui.handle_command("provider a b"))
        self.assertIn("requires exactly one", output[1])

    def test_tui_provider_unknown_name(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("provider made-up-provider"))
        self.assertIn("unknown provider", output[0])

    def test_tui_model_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("model"))
        self.assertIn("requires a model name", output[0])

    def test_tui_model_default_clears_override(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append, model="custom")

        self.assertTrue(tui.handle_command("model default"))
        self.assertIsNone(tui.model)

    def test_tui_route_model_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("route-model yes"))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_route_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("route"))
        self.assertIn("requires a task", output[0])

    def test_tui_root_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("root"))
        self.assertIn("requires exactly one path", output[0])

    def test_tui_destructive_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("destructive yes"))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_progress_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("progress enabled"))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_subagent_invalid_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("subagent enabled"))
        self.assertIn("requires 'on' or 'off'", output[0])

    def test_tui_heartbeat_with_number(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("heartbeat 5.5"))
        self.assertEqual(tui.heartbeat_seconds, 5.5)

    def test_tui_heartbeat_zero_disables(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("heartbeat 0"))
        self.assertEqual(tui.heartbeat_seconds, 0.0)

    def test_tui_heartbeat_negative_clamped(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("heartbeat -1"))
        self.assertEqual(tui.heartbeat_seconds, 0.0)

    def test_tui_heartbeat_non_numeric(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("heartbeat abc"))
        self.assertIn("must be a number", output[0])

    def test_tui_heartbeat_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("heartbeat"))
        self.assertIn("requires a seconds", output[0])

    def test_tui_status_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("status"))
        self.assertIn("requires a run id", output[0])

    def test_tui_permission_invalid_raises(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("permission"))
        self.assertIn("requires one mode", output[0])

    def test_tui_permission_invalid_mode(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("permission bogus"))
        self.assertIn("unknown permission mode", output[0])

    def test_tui_approve_requires_call_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("approve"))
        self.assertIn("requires one call id", output[0])

    def test_tui_unapprove_requires_call_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("unapprove"))
        self.assertIn("requires one call id", output[0])

    def test_tui_ask_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("ask"))
        self.assertIn("requires a task", output[0])

    def test_tui_ask_clarify_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("ask --clarify"))
        self.assertIn("requires a task", output[0])

    def test_tui_clarify_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("clarify"))
        self.assertIn("requires a task", output[0])

    def test_tui_preflight_requires_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("preflight"))
        self.assertIn("requires a task", output[0])

    def test_tui_show_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("show"))
        self.assertIn("requires a run id", output[0])

    def test_tui_resume_requires_run_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("resume"))
        self.assertIn("requires a run id", output[0])

    def test_tui_resume_unknown_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append)

            self.assertTrue(tui.handle_command("resume no-such-run"))
            self.assertIn("error:", output[0])

    def test_tui_use_requires_one_arg(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("use"))
        self.assertIn("requires exactly one database path", output[0])

    def test_tui_query_requires_cypher(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("query"))
        self.assertIn("requires a Cypher string", output[0])

    def test_tui_memory_no_subcommand(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("memory"))
        self.assertIn("requires add, list, search, or show", output[0])

    def test_tui_memory_add_no_text(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("memory add"))
        self.assertIn("requires text", output[0])

    def test_tui_memory_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append)

            self.assertTrue(tui.handle_command("memory list"))
            self.assertEqual(json.loads(output[0]), [])

    def test_tui_memory_search_no_query(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("memory search"))
        self.assertIn("requires a query", output[0])

    def test_tui_memory_show_requires_id(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("memory show"))
        self.assertIn("requires one id", output[0])

    def test_tui_memory_unknown_subcommand(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("memory delete"))
        self.assertIn("unknown memory command", output[0])

    def test_tui_runs_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            tui = TeaAgentTUI(root=tmp, input_fn=lambda _prompt: "exit", output_fn=output.append)

            self.assertTrue(tui.handle_command("runs"))
            self.assertEqual(json.loads(output[0]), [])

    def test_tui_eof_returns_zero(self) -> None:
        output = []

        def raise_eof(_prompt: str) -> str:
            raise EOFError()

        tui = TeaAgentTUI(input_fn=raise_eof, output_fn=output.append)

        exit_code = tui.run()
        self.assertEqual(exit_code, 0)
        self.assertEqual(output[-1], "bye")

    def test_tui_subagent_on_off(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("subagent on"))
        self.assertTrue(tui.subagent)
        self.assertTrue(tui.handle_command("subagent off"))
        self.assertFalse(tui.subagent)

    def test_tui_clarify_accepts_concrete_task(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)

        self.assertTrue(tui.handle_command("clarify Update docs/cli.md to document clarify command"))
        payload = json.loads(output[0])
        self.assertFalse(payload["needs_clarification"])

    def test_tui_print_header_output(self) -> None:
        output = []
        tui = TeaAgentTUI(input_fn=lambda _prompt: "exit", output_fn=output.append)
        tui._print_header()

        self.assertEqual(output[0], "TeaAgent TUI 0.1.0")

    def test_tui_status_with_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"done"}'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command("ask hello world"))
            run_id = json.loads(output[-1])["run_id"]

            self.assertTrue(tui.handle_command(f"status {run_id}"))
            status_payload = json.loads(output[-1])
            self.assertEqual(status_payload["run_id"], run_id)
            self.assertEqual(status_payload["status"], "completed")

    def test_tui_show_with_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = []
            adapter = FakeAdapter(['{"type":"final","content":"result"}'])
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command("ask task"))
            run_id = json.loads(output[-1])["run_id"]

            self.assertTrue(tui.handle_command(f"show {run_id}"))
            events = json.loads(output[-1])
            self.assertIsInstance(events, list)
            self.assertGreater(len(events), 0)

    def test_tui_ask_clarify_with_concrete_task_builds_spec(self) -> None:
        output = []
        adapter = FakeAdapter(['{"type":"final","content":"done"}'])
        tui = TeaAgentTUI(
            input_fn=lambda _prompt: "exit",
            output_fn=output.append,
            adapter_factory=lambda _provider, _model: adapter,
        )
        self.assertTrue(tui.handle_command("ask --clarify Update docs/cli.md to document clarify command"))
        payload = json.loads(output[-1])
        self.assertEqual(payload["status"], "completed")

    def test_tui_progress_sink_handles_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"nonexistent_tool","arguments":{},"call_id":"bad"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: "exit",
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )
            self.assertTrue(tui.handle_command("progress on"))
            self.assertTrue(tui.handle_command("ask broken"))

            joined = "\n".join(output)
            self.assertIn("failed:", joined)

    def test_run_tui_function(self) -> None:
        from teaagent.tui import run_tui

        commands = iter(["exit"])
        tui = TeaAgentTUI(
            database=":memory:",
            provider="gpt",
            model="test",
            root=".",
            input_fn=lambda _prompt: next(commands),
            output_fn=lambda _msg: None,
        )
        exit_code = tui.run()
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
