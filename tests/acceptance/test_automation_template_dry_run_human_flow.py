"""Teachable automation templates produce human-readable dry-run checklists."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.cli import main


def test_automation_template_dry_run_human_flow(tmp_path: Path) -> None:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(
            [
                'agent',
                'automation',
                'template',
                'repo-watch',
                '--dry-run',
                '--human',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 0
    payload = json.loads(out.getvalue())
    assert payload['status'] == 'dry_run'
    assert payload['template'] == 'repo-watch'
    assert payload['ticket']['ready'] is True
    assert payload['ticket']['provenance_digest'].startswith('sha256:')
    assert 'read-only' in payload['ticket']['allowed_toolsets']
    human = payload['human']
    assert 'repo-watch' in human
    assert 'Provenance digest:' in human
    assert 'Collector command:' in human
    assert 'Dry-run: ready' in human
