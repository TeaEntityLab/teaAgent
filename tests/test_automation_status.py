from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_status_lists_automations(tmp_path: Path) -> None:
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        main(
            [
                'agent',
                'automation',
                'add',
                'status-job',
                'Run echo hello for status coverage.',
                '--schedule',
                'every 30m',
                '--acceptance-criteria',
                'Echo prints hello.',
                '--root',
                str(tmp_path),
            ]
        )
    status_out = io.StringIO()
    with redirect_stdout(status_out):
        code = main(['agent', 'automation', 'status', '--root', str(tmp_path)])
    assert code == 0
    payload = json.loads(status_out.getvalue())
    assert payload['automation_count'] == 1
    row = payload['automations'][0]
    assert row['name'] == 'status-job'
    assert 'token_contributors' in row
    assert 'prompt_ledger' in row
