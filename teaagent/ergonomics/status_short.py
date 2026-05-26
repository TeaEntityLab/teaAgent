from __future__ import annotations

from pathlib import Path
from typing import Optional

from teaagent.daily import build_daily_brief
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore


def build_status_short(
    *,
    root: str | Path,
    provider: str,
    run_id: Optional[str] = None,
    model: Optional[str] = None,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
) -> str:
    brief = build_daily_brief(
        task='status check',
        root=root,
        provider=provider,
        model=model,
        permission_mode=permission_mode,
        context_profile='lean',
        runs_limit=3,
        readonly=True,
    )
    level = brief.token_budget.usage_level
    colour = {'green': 'G', 'yellow': 'Y', 'red': 'R'}.get(level, '?')
    pending = sum(1 for run in brief.recent_runs if run.pending_approval)
    active = run_id
    if not active and brief.recent_runs:
        for run in brief.recent_runs:
            if run.status == 'running' or str(run.status).startswith('failed'):
                active = run.run_id
                break
        if not active:
            active = brief.recent_runs[0].run_id
    store = RunStore(root, readonly=True)
    status = 'idle'
    if active:
        try:
            status = store.heartbeat_for_run(active).get('status', 'unknown')
        except FileNotFoundError:
            status = 'missing'
    return f'teaagent:{colour} pending={pending} run={active or "-"} status={status}'
