from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from teaagent import AuditLogger, FinalAnswer, RunStore
from teaagent.cli import main
from teaagent.runner import RunResult


class RunStoreTests(unittest.TestCase):
    def test_run_store_persists_and_summarizes_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record("run_started", "run-1", task="demo")
            audit.record("run_completed", "run-1", answer="done", metadata={})
            result = RunResult(
                run_id="run-1",
                final_answer=FinalAnswer("done"),
                iterations=1,
                tool_calls=0,
                status="completed",
            )

            store.logger_for_result(result, audit)
            summaries = store.list_runs()
            events = store.show_run("run-1")

            self.assertEqual(summaries[0].run_id, "run-1")
            self.assertEqual(summaries[0].status, "completed")
            self.assertEqual(summaries[0].final_answer, "done")
            self.assertEqual(events[0]["event_type"], "run_started")
            self.assertTrue((Path(tmp) / ".teaagent" / "runs" / "run-1.jsonl").exists())

    def test_task_for_run_extracts_original_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record("run_started", "run-task", task="resume me")
            audit.record("run_completed", "run-task", answer="ok", metadata={})
            store.logger_for_result(
                RunResult(run_id="run-task", final_answer=FinalAnswer("ok"), iterations=1, tool_calls=0, status="completed"),
                audit,
            )

            self.assertEqual(store.task_for_run("run-task"), "resume me")

    def test_cli_lists_and_shows_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunStore(tmp)
            audit = store.audit_logger()
            audit.record("run_started", "run-2", task="demo")
            audit.record("run_failed", "run-2", category="model_logic", message="x")
            store.logger_for_result(
                RunResult(run_id="run-2", final_answer=None, iterations=1, tool_calls=0, status="failed:model_logic"),
                audit,
            )

            list_output = io.StringIO()
            show_output = io.StringIO()
            with redirect_stdout(list_output):
                list_code = main(["agent", "runs", "--root", tmp])
            with redirect_stdout(show_output):
                show_code = main(["agent", "show", "run-2", "--root", tmp])

            self.assertEqual(list_code, 0)
            self.assertEqual(show_code, 0)
            self.assertEqual(json.loads(list_output.getvalue())[0]["run_id"], "run-2")
            self.assertEqual(json.loads(show_output.getvalue())[1]["event_type"], "run_failed")


if __name__ == "__main__":
    unittest.main()
