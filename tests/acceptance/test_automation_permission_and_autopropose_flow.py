"""AC-NEW-25: Automation permission and auto-propose continuity.

As a user, I want automation runs to preserve explicit permission mode settings
and auto-proposed skill candidates to avoid duplicate creation from the same run.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


def test_automation_permission_mode_matrix_flows_into_background_command(
    tmp_path: Path,
) -> None:
    modes = ['read-only', 'workspace-write', 'prompt', 'allow']
    for mode in modes:
        add_out = io.StringIO()
        with redirect_stdout(add_out):
            add_code = main(
                [
                    'agent',
                    'automation',
                    'add',
                    f'{mode}-job',
                    'echo permission',
                    '--schedule',
                    'every 30m',
                    '--permission-mode',
                    mode,
                    '--root',
                    str(tmp_path),
                ]
            )
        assert add_code == 0
        automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

        run_out = io.StringIO()
        with redirect_stdout(run_out):
            run_code = main(
                [
                    'agent',
                    'automation',
                    'run',
                    automation_id,
                    '--root',
                    str(tmp_path),
                ]
            )
        assert run_code == 0
        payload = json.loads(run_out.getvalue())
        assert payload['status'] in {'background_started', 'skipped_running'}
        if payload['status'] != 'background_started':
            continue
        record_path = (
            tmp_path / '.teaagent' / 'background' / f'{payload["background_id"]}.json'
        )
        record = json.loads(record_path.read_text(encoding='utf-8'))
        command = record['command']
        assert '--permission-mode' in command
        idx = command.index('--permission-mode')
        assert command[idx + 1] == mode


def test_automation_auto_propose_skill_is_idempotent_for_same_run(
    tmp_path: Path,
) -> None:
    run_out = io.StringIO()
    with (
        patch(
            'teaagent.cli.create_llm_adapter',
            return_value=FakeAdapter(
                ['{"type":"final","content":"use pytest and focused fixtures"}']
            ),
        ),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'agent',
                'run',
                'gpt',
                'write testing guidance',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    assert run_code == 0
    run_id = json.loads(run_out.getvalue())['run_id']

    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'auto-skill',
                'draft skill',
                '--schedule',
                'every 30m',
                '--auto-propose-skill',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

    bg_dir = tmp_path / '.teaagent' / 'background'
    bg_dir.mkdir(parents=True, exist_ok=True)
    bg_id = 'done-bg'
    log_path = bg_dir / f'{bg_id}.log'
    log_path.write_text(
        json.dumps({'run_id': run_id, 'status': 'completed'}) + '\n', encoding='utf-8'
    )
    (bg_dir / f'{bg_id}.json').write_text(
        json.dumps(
            {
                'background_id': bg_id,
                'pid': 2147483647,
                'command': ['noop'],
                'started_at': '2026-05-24T00:00:00+00:00',
                'log_path': str(log_path),
            }
        ),
        encoding='utf-8',
    )

    show_out = io.StringIO()
    with redirect_stdout(show_out):
        main(['agent', 'automation', 'show', automation_id, '--root', str(tmp_path)])
    spec = json.loads(show_out.getvalue())
    spec['running_background_id'] = bg_id
    automation_path = tmp_path / '.teaagent' / 'automations' / f'{automation_id}.json'
    automation_path.write_text(json.dumps(spec), encoding='utf-8')

    first_tick = io.StringIO()
    with redirect_stdout(first_tick):
        first_code = main(['agent', 'automation', 'tick', '--root', str(tmp_path)])
    assert first_code == 0

    second_tick = io.StringIO()
    with redirect_stdout(second_tick):
        second_code = main(['agent', 'automation', 'tick', '--root', str(tmp_path)])
    assert second_code == 0

    candidates_out = io.StringIO()
    with redirect_stdout(candidates_out):
        list_code = main(['skill', 'candidate', 'list', '--root', str(tmp_path)])
    assert list_code == 0
    rows = json.loads(candidates_out.getvalue())
    auto_rows = [row for row in rows if row['name'] == 'auto-skill-auto']
    assert len(auto_rows) == 1
