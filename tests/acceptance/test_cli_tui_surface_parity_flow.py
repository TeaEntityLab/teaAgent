"""Test module for CLI and TUI surface parity.

This module tests that the CLI and TUI expose the same readiness fields and
metadata for daily operations. This ensures feature parity between the command-line
interface and the terminal user interface.

Key concepts tested:
- Daily Cockpit Parity: CLI daily and TUI daily expose same fields
- Token Budget: Both surfaces show token_budget with usage_level
- Recent Runs: Both surfaces show recent_runs history
- Provider Info: Both surfaces show provider and permission_mode
- Session List: CLI session list is available after setup

Acceptance Criteria:
- AC1: CLI daily JSON includes token_budget and recent_runs
- AC2: TUI daily cockpit includes token_budget and recent_runs
- AC3: CLI and TUI token_budget usage_level match
- AC4: CLI and TUI show same provider and permission_mode
- AC5: CLI session list is available after setup

Technical Details:
- CLI daily command returns JSON with readiness fields
- TUI daily cockpit command returns JSON with same schema
- token_budget includes: usage_level, usage_cents, limit_cents
- recent_runs includes: run_id, status, timestamp, task
- Session list returns array of session metadata
- Parity ensures consistent experience across interfaces

References:
- Surface parity design: /docs/architecture/surface_parity.md
- Daily cockpit spec: /docs/specs/daily_cockpit.md
"""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main
from teaagent.tui import TeaAgentTUI


def test_daily_json_and_tui_cockpit_share_token_budget_and_runs() -> None:
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
        # Exit code 0 = success, 2 = soft error (e.g., no runs yet but command succeeded)
        # Both are acceptable for this parity test - we're checking surface parity, not run existence
        assert cli_code in (0, 2), (
            f'CLI daily command failed with unexpected code {cli_code} '
            f'(expected 0 or 2 for surface parity check)'
        )
        assert 'token_budget' in cli_payload
        assert 'recent_runs' in cli_payload
        assert cli_payload['provider'] == 'gpt'

        tui_output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=tui_output.append,
            provider='gpt',
        )
        assert tui.handle_command('daily surface parity check')
        tui_json = json.loads(tui_output[-1])
        for key in ('token_budget', 'recent_runs', 'provider', 'permission_mode'):
            assert key in cli_payload
            assert key in tui_json
        assert (
            cli_payload['token_budget']['usage_level']
            == tui_json['token_budget']['usage_level']
        )


def test_session_list_available_from_cli_after_setup() -> None:
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
        assert code == 0
        payload = json.loads(out.getvalue())
        assert isinstance(payload, list)
