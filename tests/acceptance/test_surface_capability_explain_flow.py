"""SURF-011: surfaces explain lists commands and gaps per surface."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.surface_parity import (
    IDE_COMMAND_CLI_PARITY,
    SURF002_REQUIRED_COMMANDS,
    SURFACE_EXPLAIN_SCHEMA_VERSION,
    build_surface_explain,
    format_surface_explain_human,
)


class SurfaceCapabilityExplainFlowTests(unittest.TestCase):
    def test_build_surface_explain_includes_all_surfaces(self) -> None:
        payload = build_surface_explain()
        self.assertEqual(payload['schema_version'], SURFACE_EXPLAIN_SCHEMA_VERSION)
        surfaces = payload['surfaces']
        self.assertEqual(
            set(surfaces),
            {'cli', 'tui', 'ide', 'dashboard'},
        )
        self.assertIn('agent daily', surfaces['cli']['supported'])
        self.assertIn('resume <run_id>', surfaces['tui']['supported'])
        self.assertEqual(len(surfaces['ide']['supported']), len(IDE_COMMAND_CLI_PARITY))
        self.assertEqual(
            set(surfaces['ide']['surf002_required']), SURF002_REQUIRED_COMMANDS
        )
        self.assertIn('dashboard_cockpit', surfaces['ide']['gaps'])

    def test_human_formatter_mentions_surfaces(self) -> None:
        text = format_surface_explain_human(build_surface_explain())
        self.assertIn('## cli', text)
        self.assertIn('## ide', text)
        self.assertIn('teaagent.agentDaily', text)

    def test_cli_surfaces_explain_emits_json_contract(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(['surfaces', 'explain'])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload['schema_version'], SURFACE_EXPLAIN_SCHEMA_VERSION)
        self.assertIn('surfaces', payload)

    def test_cli_surfaces_explain_human_flag(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(['surfaces', 'explain', '--human'])
        self.assertEqual(code, 0)
        self.assertIn('TeaAgent surface capabilities', out.getvalue())


if __name__ == '__main__':
    unittest.main()
