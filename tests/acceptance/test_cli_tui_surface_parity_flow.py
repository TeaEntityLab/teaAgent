"""CLI daily JSON and TUI daily cockpit expose the same readiness fields."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.tui import TeaAgentTUI


class CliTuiSurfaceParityFlowTests(unittest.TestCase):
    def test_daily_json_and_tui_cockpit_share_token_budget_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('parity surface', encoding='utf-8')
            cli_out = io.StringIO()
            with redirect_stdout(cli_out):
                cli_code = main(
                    [
                        'agent',
                        'daily',
                        'gpt',
                        'surface parity check',
                        '--root',
                        tmp,
                        '--permission-mode',
                        'read-only',
                    ]
                )
            cli_payload = json.loads(cli_out.getvalue())
            self.assertIn(cli_code, (0, 2))
            self.assertIn('token_budget', cli_payload)
            self.assertIn('recent_runs', cli_payload)
            self.assertEqual(cli_payload['provider'], 'gpt')

            tui_output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=tui_output.append,
                provider='gpt',
            )
            self.assertTrue(tui.handle_command('daily surface parity check'))
            tui_json = json.loads(tui_output[-1])
            for key in ('token_budget', 'recent_runs', 'provider', 'permission_mode'):
                self.assertIn(key, cli_payload)
                self.assertIn(key, tui_json)
            self.assertEqual(
                cli_payload['token_budget']['usage_level'],
                tui_json['token_budget']['usage_level'],
            )

    def test_session_list_available_from_cli_after_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        'setup',
                        '--root',
                        tmp,
                        '--provider',
                        'gpt',
                        '--api-key',
                        'sk-parity',
                        '--permission-mode',
                        'read-only',
                    ]
                )
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(['session', 'list', '--root', tmp])
            self.assertEqual(code, 0)
            payload = json.loads(out.getvalue())
            self.assertIsInstance(payload, list)


if __name__ == '__main__':
    unittest.main()
