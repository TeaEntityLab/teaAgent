from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


class CLITests(unittest.TestCase):
    def test_doctor_graphqlite_outputs_json(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["doctor", "graphqlite"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])

    def test_graphqlite_smoke_runs_real_query(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["graphqlite", "smoke"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload, [{"n.name": "TeaAgent"}])

    def test_doctor_model_reports_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = main(["doctor", "model", "gpt"])
                payload = json.loads(output.getvalue())
                self.assertEqual(exit_code, 1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["provider"], "gpt")

    def test_doctor_model_ok_when_key_set(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}, clear=True):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["doctor", "model", "gpt"])
            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["provider"], "gpt")

    def test_model_smoke_outputs_provider_and_content(self) -> None:
        adapter = FakeAdapter(["hello from fake"])
        output = io.StringIO()

        with patch("teaagent.cli.create_llm_adapter", return_value=adapter), redirect_stdout(output):
            exit_code = main(["model", "smoke", "gpt", "--prompt", "say hi", "--max-tokens", "16"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["provider"], "fake")
        self.assertEqual(payload["model"], "fake-model")
        self.assertEqual(payload["content"], "hello from fake")

    def test_cli_help_includes_description(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("TeaAgent harness", output.getvalue())

    def test_cli_version_outputs_version(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["--version"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("teaagent", output.getvalue())

    def test_graphqlite_query_executes_cypher(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(["graphqlite", "query", "MATCH (n:SmokeTest) RETURN n.name"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIsInstance(payload, list)

    def test_ultrawork_show_unknown_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ultrawork", "show", "unknown-id", "--root", tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "error")

    def test_ultrawork_stop_unknown_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["ultrawork", "stop", "unknown-id", "--root", tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "error")

    def test_agent_status_unknown_run_id_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["agent", "status", "no-such-run", "--root", tmp])

            self.assertEqual(exit_code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "error")


if __name__ == "__main__":
    unittest.main()
