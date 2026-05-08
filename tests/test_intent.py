from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
import unittest

from teaagent.cli import main
from teaagent.intent import build_task_spec, clarify_task


class IntentTests(unittest.TestCase):
    def test_clarify_task_flags_vague_task(self) -> None:
        result = clarify_task("improve stuff")

        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.question, "What action do you want TeaAgent to take?")
        self.assertIn("intent", result.missing)

    def test_clarify_task_accepts_concrete_task(self) -> None:
        result = clarify_task("Update docs/cli.md to document clarify command without changing APIs and verify tests pass")

        self.assertFalse(result.needs_clarification)
        self.assertEqual(result.question, None)

    def test_build_task_spec_includes_missing_fields(self) -> None:
        clarification = clarify_task("fix tests")

        spec = build_task_spec("fix tests", clarification)

        self.assertIn("Clarified task specification", spec)
        self.assertIn("TASK: fix tests", spec)
        self.assertIn("MISSING:", spec)

    def test_cli_clarify_outputs_json(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["clarify", "improve stuff"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["needs_clarification"])
        self.assertEqual(payload["question"], "What action do you want TeaAgent to take?")

    def test_cli_agent_run_clarify_stops_before_model_when_ambiguous(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["agent", "run", "gpt", "improve stuff", "--clarify"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "needs_clarification")
        self.assertTrue(payload["clarification"]["needs_clarification"])


if __name__ == "__main__":
    unittest.main()
