"""Test module for automation context chaining and handoff flow.

This module tests the automation chain system, which enables downstream automations
to receive context from upstream automations. This allows automations to be composed
into pipelines where later automations can leverage results and summaries from earlier
ones.

Key concepts tested:
- Context Chaining: Downstream automations reference upstream automation IDs via context_from
- Handoff Persistence: Upstream results are persisted for downstream consumption
- Task Enrichment: Downstream tasks are enriched with upstream summaries
- CLI Integration: Automation add command supports --context-from flag
- Dry-Run Validation: Chained automations show upstream handoff preview in dry-run

Acceptance Criteria:
- AC1: Downstream automation can reference upstream via context_from field
- AC2: Upstream results are persisted via persist_automation_handoff
- AC3: Downstream task includes upstream summary in the task prompt
- AC4: CLI --context-from flag links automations in the spec
- AC5: Dry-run shows upstream_handoff_preview in the ticket

Technical Details:
- AutomationStore manages automation specs with context_from references
- persist_automation_handoff saves upstream results to .teaagent/automation_handoffs/
- _run_automation_once injects upstream context into the task prompt
- Context includes: collector_summary, summary, and upstream metadata
- Chaining enables automation pipelines (e.g., collector → triage → action)

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Chaining spec: /docs/specs/automation_chaining.md
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from teaagent.automation_chain import persist_automation_handoff
from teaagent.automations import AutomationStore
from teaagent.cli import main
from teaagent.cli._handlers._agent import _run_automation_once


def test_automation_context_from_chain_flow(tmp_path: Path) -> None:
    store = AutomationStore(tmp_path)
    upstream = store.create(
        name='repo-collector',
        task='Emit JSON {"wake_agent":true,"summary":"commit abc1234"} from git log -1.',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        collector_command='python3 -c "print(1)"',
    )
    persist_automation_handoff(
        tmp_path,
        upstream,
        collector_summary='commit abc1234 detected',
        summary='commit abc1234 detected',
    )
    downstream = store.create(
        name='repo-triage',
        task='Decide if the agent should act on the upstream summary.',
        schedule='every 1h',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        context_from=upstream.automation_id,
    )

    with patch(
        'teaagent.cli._handlers._agent.automation._start_automation_background_run',
        return_value={
            'background_id': 'bg-down',
            'pid': 1,
            'log_path': str(tmp_path / 'down.log'),
        },
    ) as start_bg:
        payload = _run_automation_once(str(tmp_path), downstream)

    assert payload['status'] == 'background_started'
    start_bg.assert_called_once()
    task_arg = start_bg.call_args.kwargs['task']
    assert 'abc1234' in task_arg
    assert 'Upstream automation context' in task_arg

    dry_out = io.StringIO()
    with redirect_stdout(dry_out):
        code = main(
            [
                'agent',
                'automation',
                'add',
                'draft',
                'Dry-run chained automation with explicit acceptance checks listed',
                '--schedule',
                'every 1h',
                '--context-from',
                upstream.automation_id,
                '--acceptance-criteria',
                'Downstream task mentions upstream summary.',
                '--dry-run',
                '--root',
                str(tmp_path),
            ]
        )
    assert code == 0
    dry_payload = json.loads(dry_out.getvalue())
    assert dry_payload['ticket']['context_from'] == upstream.automation_id
    assert 'abc1234' in dry_payload['ticket']['upstream_handoff_preview']
