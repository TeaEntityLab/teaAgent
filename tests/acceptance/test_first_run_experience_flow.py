"""AC-NEW-15: First-run initialization experience flow.

As a first-time TeaAgent user, I want `teaagent init` to bootstrap essential
workspace files and return actionable metadata, so I can run the agent without
manual scaffolding.

Acceptance criteria:
- `init` creates `.teaagent/config.json`.
- `init` creates `AGENTS.md` when missing.
- `init` does not overwrite an existing `AGENTS.md`.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_first_run_init_bootstraps_config_and_agents_md(tmp_path: Path) -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            [
                'init',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-test-first-run',
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['ok'] is True
    assert (tmp_path / '.teaagent' / 'config.json').exists()
    assert (tmp_path / 'AGENTS.md').exists()
    assert payload['agents_md_status'] in {'created', 'existing'}
    assert payload['agents_md_path'] == str(tmp_path / 'AGENTS.md')


def test_first_run_init_preserves_existing_agents_md(tmp_path: Path) -> None:
    agents_path = tmp_path / 'AGENTS.md'
    agents_path.write_text('custom project rules\n', encoding='utf-8')

    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            [
                'init',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-test-first-run',
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['agents_md_status'] == 'existing'
    assert agents_path.read_text(encoding='utf-8') == 'custom project rules\n'


def test_first_run_init_returns_onboarding_checklist(tmp_path: Path) -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            [
                'init',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-test-first-run',
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    checklist = payload.get('next_steps')
    assert isinstance(checklist, list)
    assert len(checklist) >= 3
    assert any('doctor model gpt' in step for step in checklist)
    assert any('agent run gpt' in step and 'read-only' in step for step in checklist)
    assert any('mcp serve --http --port 7330' in step for step in checklist)
