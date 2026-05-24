"""Promote quarantined automations after owner attestation."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.automations import AutomationStore
from teaagent.cli import main


def test_automation_promote_quarantined_flow(tmp_path: Path) -> None:
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'web-watcher',
                'Summarize external webhook payload and write notes.txt',
                '--schedule',
                'every 30m',
                '--write-source',
                'web_message',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

    list_out = io.StringIO()
    with redirect_stdout(list_out):
        list_code = main(
            ['agent', 'automation', 'list', '--quarantined', '--root', str(tmp_path)]
        )
    assert list_code == 0
    assert json.loads(list_out.getvalue())[0]['automation_id'] == automation_id

    promote_out = io.StringIO()
    with redirect_stdout(promote_out):
        promote_code = main(
            [
                'agent',
                'automation',
                'promote',
                automation_id,
                '--i-attest-untrusted-write',
                '--root',
                str(tmp_path),
            ]
        )
    assert promote_code == 0
    assert json.loads(promote_out.getvalue())['status'] == 'promoted'
    active = AutomationStore(tmp_path).show(automation_id)
    assert active.enabled is True
