"""automation status exposes prompt ledger, token contributors, and gate reasons."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_status_observability_flow(tmp_path: Path) -> None:
    add_out = io.StringIO()
    with redirect_stdout(add_out):
        add_code = main(
            [
                'agent',
                'automation',
                'add',
                'obs-job',
                'Run status observability check with explicit acceptance criteria.',
                '--schedule',
                'every 30m',
                '--acceptance-criteria',
                'Status JSON includes token_contributors and prompt_ledger keys.',
                '--requires-subagent',
                '--root',
                str(tmp_path),
            ]
        )
    assert add_code == 0
    automation_id = json.loads(add_out.getvalue())['automation']['automation_id']

    status_out = io.StringIO()
    with redirect_stdout(status_out):
        status_code = main(
            [
                'agent',
                'automation',
                'status',
                automation_id,
                '--root',
                str(tmp_path),
            ]
        )
    assert status_code == 0
    row = json.loads(status_out.getvalue())['automation']
    assert row['requires_subagent'] is True
    assert 'token_contributors' in row
    assert 'prompt_ledger' in row
    assert 'blocked_gate_reason' in row
    assert 'last_output_preview' in row
