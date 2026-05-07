from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from teaagent import (
    AgentRunner,
    AuditLogger,
    ContextCompactor,
    Document,
    EvalCase,
    FinalAnswer,
    InMemoryRetriever,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
    TraceRecorder,
    agentic_retrieve,
    build_aibom,
    review_skill,
    run_eval,
)


class P1PrimitiveTests(unittest.TestCase):
    def test_trace_recorder_receives_audit_events(self) -> None:
        audit = AuditLogger()
        trace = TraceRecorder()
        audit.add_sink(trace.handle_event)
        registry = ToolRegistry()
        registry.register(
            name="echo",
            description="Echo value.",
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            output_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            annotations=ToolAnnotations(read_only=True, idempotent=True),
            handler=lambda args: {"value": args["value"]},
        )
        runner = AgentRunner(registry=registry, audit=audit)

        def decide(context):
            if not context["observations"]:
                return ToolRequest(tool_name="echo", arguments={"value": "traced"}, call_id="call-1")
            return FinalAnswer(content="done")

        result = runner.run(task="trace me", decide=decide, run_id="trace-run")

        self.assertEqual(result.status, "completed")
        self.assertIn("agent.run", [span.name for span in trace.spans])
        tool_span = next(span for span in trace.spans if span.name == "tool.call")
        tool_completed = next(event for event in audit.events if event.event_type == "tool_call_completed")
        self.assertEqual(tool_span.ended_at, tool_completed.created_at)

    def test_context_compactor_pins_memory_keys(self) -> None:
        context = {
            "task": "long task",
            "observations": [
                {"tool_name": "a", "result": {"value": "1"}},
                {"tool_name": "b", "result": {"transaction_id": "tx-123"}},
                {"tool_name": "c", "result": {"value": "3"}},
            ],
        }

        result = ContextCompactor(recent_observations=1, memory_keys=("transaction_id",)).compact(context)

        self.assertEqual(len(result.context["observations"]), 1)
        self.assertEqual(result.pinned["transaction_id"], "tx-123")
        self.assertIn("a returned", result.summary)

    def test_skill_review_and_aibom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\nSee REFERENCE.md.\n",
                encoding="utf-8",
            )
            server_card = Path(tmp) / "server-card.json"
            server_card.write_text("{}\n", encoding="utf-8")

            review = review_skill(skill_dir)
            manifest = build_aibom(
                model="test-model",
                model_version="0",
                skill_paths=[skill_dir],
                mcp_server_card=server_card,
            )

            self.assertTrue(review.passed)
            self.assertEqual(len(manifest.components), 3)
            self.assertTrue(manifest.components[1].digest.startswith("sha256:"))

    def test_offline_eval_reports_pass_rate(self) -> None:
        report = run_eval(
            [
                EvalCase(name="ok", task="say hello", expected_contains=("hello",)),
                EvalCase(name="bad", task="say bye", expected_contains=("bye",)),
            ],
            lambda case: "hello world" if case.name == "ok" else "nope",
        )

        self.assertFalse(report.passed)
        self.assertEqual(report.pass_rate, 0.5)
        self.assertEqual(report.results[1].failures, ("bye",))

    def test_agentic_retrieve_routes_and_fuses_results(self) -> None:
        retriever = InMemoryRetriever(
            [
                Document(doc_id="s1", text="semantic policy for agent skills", source="semantic"),
                Document(doc_id="d1", text="revenue table shows cost changes", source="structured"),
                Document(doc_id="w1", text="latest agent news today", source="web"),
            ]
        )

        results = agentic_retrieve("compare revenue and latest agent news", retriever)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].document.doc_id, "d1")
        self.assertIn("w1", {result.document.doc_id for result in results})


if __name__ == "__main__":
    unittest.main()
