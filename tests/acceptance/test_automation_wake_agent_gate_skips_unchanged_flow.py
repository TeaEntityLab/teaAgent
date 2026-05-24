"""AC-NEW: Collector wake_agent=false skips LLM automation runs."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_wake_agent_gate_skips_unchanged_flow(tmp_path: Path) -> None:
    collector = tmp_path / 'collector.py'
    collector.write_text(
        'import json\nprint(json.dumps({"wake_agent": False, "summary": "no new commits"}))\n',
        encoding='utf-8',
    )
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'repo-watch',
                'Summarize new commits when the collector reports changes.',
                '--schedule',
                'every 30m',
                '--collector-command',
                f'{sys.executable} {collector}',
                '--acceptance-criteria',
                'When wake_agent is true, background run starts.',
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
    assert payload['status'] == 'skipped_no_wake'
    assert payload['collector']['wake_agent'] is False
    bg_dir = tmp_path / '.teaagent' / 'background'
    assert not list(bg_dir.glob('*.json')) if bg_dir.is_dir() else True
