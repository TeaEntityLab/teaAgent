from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
import unittest

from teaagent.cli import main
from teaagent.tui import TeaAgentTUI


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

    def test_cli_tui_help_in_parser(self) -> None:
        output = io.StringIO()

        with self.assertRaises(SystemExit) as context, redirect_stdout(output):
            main(["tui", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Start an interactive terminal UI", output.getvalue())


if __name__ == "__main__":
    unittest.main()
