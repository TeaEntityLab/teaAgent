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


if __name__ == "__main__":
    unittest.main()
