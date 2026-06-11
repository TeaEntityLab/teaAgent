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
    # Verify init command succeeds
    assert exit_code == 0, f'Expected init to succeed, got exit code {exit_code}'
    # Verify payload indicates success
    assert payload['ok'] is True, f'Expected payload ok=True, got {payload["ok"]}'
    # Verify config.json was created
    assert (tmp_path / '.teaagent' / 'config.json').exists(), (
        'Expected .teaagent/config.json to be created'
    )
    # Verify AGENTS.md was created
    assert (tmp_path / 'AGENTS.md').exists(), 'Expected AGENTS.md to be created'
    # Verify agents_md_status is either created or existing
    assert payload['agents_md_status'] in {'created', 'existing'}, (
        f'Expected agents_md_status to be "created" or "existing", got {payload["agents_md_status"]!r}'
    )
    # Verify agents_md_path points to correct location
    assert payload['agents_md_path'] == str(tmp_path / 'AGENTS.md'), (
        f'Expected agents_md_path to point to AGENTS.md, got {payload["agents_md_path"]!r}'
    )


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
    # Verify init command succeeds when AGENTS.md already exists
    assert exit_code == 0, (
        f'Expected init to succeed with existing AGENTS.md, got exit code {exit_code}'
    )
    # Verify agents_md_status is "existing" (not overwritten)
    assert payload['agents_md_status'] == 'existing', (
        f'Expected agents_md_status "existing" when AGENTS.md exists, got {payload["agents_md_status"]!r}'
    )
    # Verify existing AGENTS.md content is preserved
    assert agents_path.read_text(encoding='utf-8') == 'custom project rules\n', (
        'Expected existing AGENTS.md content to be preserved'
    )


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
    # Verify init command succeeds
    assert exit_code == 0, f'Expected init to succeed, got exit code {exit_code}'
    checklist = payload.get('next_steps')
    # Verify next_steps is a list
    assert isinstance(checklist, list), (
        f'Expected next_steps to be a list, got {type(checklist).__name__}'
    )
    # Verify checklist has at least 3 items
    assert len(checklist) >= 3, (
        f'Expected at least 3 checklist items, got {len(checklist)}'
    )
    # Verify checklist includes setup step
    assert any('teaagent setup' in step for step in checklist), (
        'Expected checklist to include "teaagent setup" step'
    )
    # Verify checklist includes daily dry-run step
    assert any('daily' in step and 'dry-run' in step for step in checklist), (
        'Expected checklist to include daily dry-run step'
    )
    # Verify checklist includes MCP doctor wizard step
    assert any('doctor mcp' in step and 'wizard' in step for step in checklist), (
        'Expected checklist to include MCP doctor wizard step'
    )
