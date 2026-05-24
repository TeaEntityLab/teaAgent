"""AC-NEW: Automation run tickets must be self-contained before scheduling."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_dry_run_fails_without_acceptance_criteria(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'automation',
                'add',
                'doc-check',
                'Run scripts/refresh_competitive_docs.py --check and summarize drift.',
                '--schedule',
                'every 30m',
                '--dry-run',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 1
    payload = json.loads(out.getvalue())
    assert payload['ticket']['ready'] is False
    assert any('acceptance_criteria' in err for err in payload['ticket']['errors'])


def test_automation_dry_run_rejects_vague_task(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'automation',
                'add',
                'vague',
                '照你知道的做',
                '--schedule',
                'every 30m',
                '--acceptance-criteria',
                'Should not matter',
                '--dry-run',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 1
    payload = json.loads(out.getvalue())
    assert any('not self-contained' in err for err in payload['ticket']['errors'])


def test_automation_background_run_uses_no_auto_skills_by_default(
    tmp_path: Path,
) -> None:
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'repo-watch',
                'List git log -1 --oneline and write summary to automation-output.txt',
                '--schedule',
                'every 30m',
                '--acceptance-criteria',
                'Creates automation-output.txt with one commit line.',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

    run_out = io.StringIO()
    with redirect_stdout(run_out):
        run_code = main(
            ['agent', 'automation', 'run', automation_id, '--root', str(tmp_path)]
        )
    assert run_code == 0
    payload = json.loads(run_out.getvalue())
    if payload['status'] != 'background_started':
        return
    record_path = (
        tmp_path / '.teaagent' / 'background' / f'{payload["background_id"]}.json'
    )
    command = json.loads(record_path.read_text(encoding='utf-8'))['command']
    assert '--no-auto-skills' in command
