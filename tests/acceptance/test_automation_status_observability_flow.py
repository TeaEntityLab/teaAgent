"""Test module for automation status observability.

This module tests that the automation status command exposes detailed observability
information including prompt ledger, token contributors, and gate reasons. This enables
operators to understand why automations are blocked, what resources they consume,
and what prompts are being used.

Key concepts tested:
- Status Exposure: Automation status includes token_contributors and prompt_ledger
- Gate Reasons: Status shows blocked_gate_reason when automation is blocked
- Output Preview: Status includes last_output_preview for recent runs
- Subagent Flag: Status exposes requires_subagent configuration
- CLI Integration: Automation status command returns structured JSON

Acceptance Criteria:
- AC1: Automation status includes token_contributors key
- AC2: Automation status includes prompt_ledger key
- AC3: Automation status includes blocked_gate_reason key
- AC4: Automation status includes last_output_preview key
- AC5: Automation status exposes requires_subagent flag

Technical Details:
- AutomationStore stores status metadata including observability fields
- token_contributors tracks which components contributed to token usage
- prompt_ledger records prompt templates and their versions
- blocked_gate_reason indicates why an automation is blocked (e.g., budget, schedule)
- last_output_preview shows the most recent output for quick inspection
- Status is computed from spec, recent runs, and gate state

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Observability spec: /docs/specs/automation_observability.md
"""

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
