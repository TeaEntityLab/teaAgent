from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
import unittest

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


if __name__ == "__main__":
    unittest.main()
