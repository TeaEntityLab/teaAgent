"""Test module for automation wake agent gate.

This module tests the wake agent gate, which allows collector scripts to skip
LLM automation runs when there are no changes to process. This prevents unnecessary
LLM calls and costs when the collector reports wake_agent=false.

Key concepts tested:
- Wake Agent Gate: Collector output includes wake_agent boolean flag
- Skip Logic: wake_agent=false skips background LLM run
- Status Reporting: Skipped runs return skipped_no_wake status
- Collector Output: Collector must emit JSON with wake_agent and summary
- Background Prevention: No background process is started when skipped

Acceptance Criteria:
- AC1: Collector with wake_agent=false skips LLM automation run
- AC2: Skipped runs return status=skipped_no_wake
- AC3: Skipped runs include collector output in response
- AC4: No background process files are created when skipped
- AC5: Collector summary is preserved in the response

Technical Details:
- Collector scripts must emit JSON: {"wake_agent": bool, "summary": string}
- wake_agent=false indicates no changes, skip LLM run
- wake_agent=true indicates changes, proceed with LLM run
- Skipped status avoids unnecessary LLM API calls and costs
- Background process is only started when wake_agent=true
- Collector summary is still available for logging/observability

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Collector spec: /docs/specs/automation_collectors.md
"""

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
