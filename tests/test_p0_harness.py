from __future__ import annotations

import unittest

from teaagent import (
    AgentRunner,
    ApprovalPolicy,
    AuditLogger,
    FinalAnswer,
    RunBudget,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
)


INPUT_SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "string"}},
    "required": ["value"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "string"}},
    "required": ["value"],
}


def build_registry(*, destructive: bool = False) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name="pilot_echo",
        description="Return the supplied value for pilot validation.",
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only=not destructive,
            destructive=destructive,
            idempotent=True,
        ),
        handler=lambda args: {"value": args["value"]},
    )
    return registry


class P0HarnessTests(unittest.TestCase):
    def test_runner_executes_registered_tool_and_audits_result(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(), audit=audit)

        def decide(context):
            if not context["observations"]:
                return ToolRequest(tool_name="pilot_echo", arguments={"value": "ok"})
            return FinalAnswer(content=context["observations"][0]["result"]["value"])

        result = runner.run(task="echo ok", decide=decide, run_id="run-1")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_answer.content, "ok")
        self.assertIn("tool_call_completed", [event.event_type for event in audit.events])

    def test_destructive_tool_requires_exact_call_approval(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(destructive=True), audit=audit)

        def decide(_context):
            return ToolRequest(
                tool_name="pilot_echo",
                arguments={"value": "delete"},
                call_id="call-1",
            )

        result = runner.run(task="destructive action", decide=decide, run_id="run-2")

        self.assertEqual(result.status, "failed:permission")
        self.assertEqual(audit.events[-1].payload["category"], "permission")

    def test_approved_destructive_tool_can_run(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=build_registry(destructive=True),
            audit=audit,
            approval_policy=ApprovalPolicy(frozenset({"call-1"})),
        )

        def decide(context):
            if not context["observations"]:
                return ToolRequest(
                    tool_name="pilot_echo",
                    arguments={"value": "approved"},
                    call_id="call-1",
                )
            return FinalAnswer(content="done")

        result = runner.run(task="approved action", decide=decide, run_id="run-3")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.tool_calls, 1)

    def test_iteration_budget_stops_non_terminating_agent(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(
            registry=build_registry(),
            audit=audit,
            budget=RunBudget(max_iterations=2, max_tool_calls=5),
        )

        def decide(_context):
            return ToolRequest(tool_name="pilot_echo", arguments={"value": "loop"})

        result = runner.run(task="loop forever", decide=decide, run_id="run-4")

        self.assertEqual(result.status, "failed:model_logic")
        self.assertEqual(result.iterations, 2)

    def test_schema_rejects_unexpected_arguments(self) -> None:
        audit = AuditLogger()
        runner = AgentRunner(registry=build_registry(), audit=audit)

        def decide(_context):
            return ToolRequest(
                tool_name="pilot_echo",
                arguments={"value": "ok", "extra": "blocked"},
            )

        result = runner.run(task="bad schema", decide=decide, run_id="run-5")

        self.assertEqual(result.status, "failed:model_logic")


if __name__ == "__main__":
    unittest.main()
