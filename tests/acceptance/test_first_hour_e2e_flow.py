"""First-hour daily loop: setup -> daily -> plan -> edit -> test evidence -> undo."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main

_GIT_ENV = {
    'GIT_AUTHOR_NAME': 'TeaAgent Acceptance',
    'GIT_AUTHOR_EMAIL': 'teaagent@acceptance.test',
    'GIT_COMMITTER_NAME': 'TeaAgent Acceptance',
    'GIT_COMMITTER_EMAIL': 'teaagent@acceptance.test',
}


def test_first_hour_setup_daily_plan_edit_undo(tmp_path: Path) -> None:
    calc = tmp_path / 'calc.py'
    test_file = tmp_path / 'test_calc.py'
    calc.write_text('def add(a, b):\n    return a - b\n', encoding='utf-8')
    test_file.write_text(
        'from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n',
        encoding='utf-8',
    )
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'add', 'calc.py', 'test_calc.py'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'commit', '-m', 'baseline'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )

    with redirect_stdout(io.StringIO()):
        setup_code = main(
            [
                'setup',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-first-hour',
                '--permission-mode',
                'read-only',
            ]
        )
    assert setup_code == 0
    assert (tmp_path / '.teaagent' / 'config.toml').is_file()

    daily_out = io.StringIO()
    with redirect_stdout(daily_out):
        daily_code = main(
            [
                'agent',
                'daily',
                'gpt',
                'plan calc fix for first hour',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    daily_payload = json.loads(daily_out.getvalue())
    assert daily_code in (0, 2)
    assert daily_payload['permission_mode'] == 'read-only'
    assert 'token_budget' in daily_payload

    plan_out = io.StringIO()
    with redirect_stdout(plan_out):
        plan_code = main(
            [
                'agent',
                'preflight',
                'gpt',
                'Plan fix for calc.py without editing yet',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    assert plan_code == 0
    assert json.loads(plan_out.getvalue())['context_pack']['read_only'] is True

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"calc.py"},"call_id":"read-calc"}',
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_write_file',
                    'arguments': {
                        'path': 'calc.py',
                        'content': 'def add(a, b):\n    return a + b\n',
                    },
                    'call_id': 'fix-calc',
                }
            ),
            '{"type":"final","content":"calc fixed; rerun pytest locally to verify"}',
        ]
    )
    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'agent',
                'run',
                'gpt',
                'Fix calc.py so pytest passes',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'workspace-write',
                '--skip-plan-check',
                '--max-iterations',
                '8',
                '--max-tool-calls',
                '8',
            ]
        )
    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0
    assert run_payload['status'] == 'completed'
    assert 'a + b' in calc.read_text(encoding='utf-8')

    pytest_result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert pytest_result.returncode == 0

    show_out = io.StringIO()
    with redirect_stdout(show_out):
        show_code = main(
            [
                'agent',
                'show',
                run_payload['run_id'],
                '--root',
                str(tmp_path),
            ]
        )
    assert show_code == 0
    show_payload = json.loads(show_out.getvalue())
    assert isinstance(show_payload, list)
    assert any(event.get('run_id') == run_payload['run_id'] for event in show_payload)

    undo_out = io.StringIO()
    with redirect_stdout(undo_out):
        undo_code = main(
            ['agent', 'undo', run_payload['run_id'], '--root', str(tmp_path)]
        )
    undo_payload = json.loads(undo_out.getvalue())
    assert undo_code == 0
    assert undo_payload['status'] == 'restored'
    assert 'a - b' in calc.read_text(encoding='utf-8')
