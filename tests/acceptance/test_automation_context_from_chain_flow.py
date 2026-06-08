"""context_from chains upstream handoff into downstream automation agent tasks."""

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
