"""AC-NEW: no-agent automations run collector only without LLM."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_no_agent_automation_delivers_script_output_flow(tmp_path: Path) -> None:
    collector = tmp_path / 'collector.py'
    collector.write_text(
        'import json, sys\n'
        'print(json.dumps({"wake_agent": True, "summary": "drift detected"}))\n'
        'sys.exit(0)\n',
        encoding='utf-8',
    )
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'docs-drift',
                'Run docs drift collector and record structured output.',
                '--schedule',
                'every 30m',
                '--collector-command',
                f'{sys.executable} {collector}',
                '--no-agent',
                '--acceptance-criteria',
                'Collector exits 0 and summary mentions drift.',
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
    assert payload['status'] == 'collector_ok'
    assert payload['collector']['summary'] == 'drift detected'
    bg_dir = tmp_path / '.teaagent' / 'background'
    assert not list(bg_dir.glob('*.json')) if bg_dir.is_dir() else True
