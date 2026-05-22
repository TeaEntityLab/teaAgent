"""First-session guided setup: setup -> guidance -> capabilities -> daily dry-run."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_first_session_setup_smoke(tmp_path: Path) -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        setup_code = main(
            [
                'setup',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-acceptance-setup',
                '--permission-mode',
                'read-only',
                '--write-env',
            ]
        )
    setup_payload = json.loads(output.getvalue())
    assert setup_code == 0
    assert setup_payload['ok'] is True
    assert setup_payload['mode'] == 'setup'
    assert setup_payload['safe_command']
    assert 'next_steps' in setup_payload and setup_payload['next_steps']
    assert 'sk-acceptance-setup' not in json.dumps(setup_payload)

    output = io.StringIO()
    with redirect_stdout(output):
        guidance_code = main(['guidance', '--root', str(tmp_path)])
    assert guidance_code == 0

    output = io.StringIO()
    with redirect_stdout(output):
        caps_code = main(['model', 'capabilities', '--per-model', '--provider', 'gpt'])
    assert caps_code == 0

    output = io.StringIO()
    with redirect_stdout(output):
        daily_code = main(
            [
                'daily',
                'readiness',
                '--root',
                str(tmp_path),
                '--dry-run',
            ]
        )
    daily_payload = json.loads(output.getvalue())
    assert daily_code == 0
    assert daily_payload.get('dry_run') is True or 'token_budget' in daily_payload

    output = io.StringIO()
    with redirect_stdout(output):
        recipes_code = main(['recipes', 'list'])
    assert recipes_code == 0

    output = io.StringIO()
    with redirect_stdout(output):
        sessions_code = main(['session', 'list', '--root', str(tmp_path)])
    assert sessions_code == 0


def test_init_wizard_alias_matches_setup_contract(tmp_path: Path) -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            [
                'init',
                '--wizard',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-wizard-alias',
                '--permission-mode',
                'read-only',
            ]
        )
    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['mode'] == 'setup'
    assert 'checks' in payload
    assert 'files_written' in payload


def test_run_without_setup_suggests_recovery(tmp_path: Path) -> None:
    import os

    import pytest

    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(SystemExit) as exc:
            main(['run', 'task without setup', '--root', str(tmp_path)])
        assert 'teaagent setup' in str(exc.value)
    finally:
        os.chdir(previous)
