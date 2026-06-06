"""Default progress summaries for long-running agent work (WS1-003)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from teaagent.run_store import RunStore


@dataclass(frozen=True)
class RunProgressSummary:
    run_id: str
    phase: str
    last_tool: str | None
    next_action: str
    elapsed_seconds: float | None
    budget_remaining_cents: int | None
    budget_cap_cents: int | None
    cost_cents: int
    iteration: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _elapsed_seconds(
    started_at: str | None, *, now: datetime | None = None
) -> float | None:
    start = _parse_timestamp(started_at)
    if start is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - start).total_seconds())


def build_run_progress_summary(
    store: RunStore,
    run_id: str,
    *,
    now: datetime | None = None,
) -> RunProgressSummary:
    events = store.show_run(run_id)
    started_at: str | None = None
    last_tool: str | None = None
    iteration: int | None = None
    cost_cents = 0
    budget_cap_cents: int | None = None
    phase = 'unknown'
    pending_tool: str | None = None

    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get('event_type')
        payload = event.get('payload')
        if not isinstance(payload, dict):
            payload = {}

        if event_type == 'run_started':
            started_at = event.get('created_at') or event.get('timestamp') or started_at
            cap = payload.get('max_estimated_cost_cents')
            if isinstance(cap, int):
                budget_cap_cents = cap
            elif cap is None:
                budget_cap_cents = None
            phase = 'running'
        elif event_type == 'iteration_started':
            raw = payload.get('iteration')
            if isinstance(raw, int):
                iteration = raw
        elif event_type in {'tool_call_started', 'tool_call_completed'}:
            tool_name = payload.get('tool_name')
            if isinstance(tool_name, str):
                last_tool = tool_name
        elif event_type == 'tool_call_pending_approval':
            tool_name = payload.get('tool_name')
            if isinstance(tool_name, str):
                pending_tool = tool_name
            phase = 'pending_approval'
        elif event_type == 'run_paused':
            phase = 'pending_approval'
        elif event_type == 'run_completed':
            phase = 'completed'
            cost = payload.get('cost_cents')
            if isinstance(cost, (int, float)):
                cost_cents = int(cost)
        elif event_type == 'run_failed':
            phase = 'failed'
            cost = payload.get('cost_cents')
            if isinstance(cost, (int, float)):
                cost_cents = int(cost)
        elif event_type == 'run_cancelled':
            phase = 'cancelled'

        for key in ('cost_cents', 'total_cost_cents'):
            value = payload.get(key)
            if isinstance(value, (int, float)):
                cost_cents = max(cost_cents, int(value))

    heartbeat = store.heartbeat_for_run(run_id)
    heartbeat_status = heartbeat.get('status')
    if isinstance(heartbeat_status, str) and heartbeat_status:
        if heartbeat_status == 'pending_approval':
            phase = 'pending_approval'
        elif heartbeat_status == 'running' and phase == 'unknown':
            phase = 'running'
        elif heartbeat_status.startswith('failed'):
            phase = 'failed'
        elif heartbeat_status == 'completed' and phase == 'unknown':
            phase = 'completed'

    if phase == 'pending_approval':
        next_action = (
            f'Approve pending tool {pending_tool or last_tool or "call"} '
            f'(`teaagent approval pending --human`)'
        )
    elif phase == 'running':
        next_action = 'Wait for model/tool loop or attach with `teaagent agent attach <run_id> --follow`'
    elif phase == 'completed':
        next_action = (
            'Review receipt with `teaagent agent status <run_id> --evidence --human`'
        )
    elif phase == 'failed':
        next_action = (
            'Inspect failure with `teaagent agent status <run_id> --evidence --human`'
        )
    elif phase == 'cancelled':
        next_action = 'Start a fresh run or resume if checkpoint exists'
    else:
        next_action = 'Inspect run audit trail'

    budget_remaining: int | None
    if budget_cap_cents is None:
        budget_remaining = None
    else:
        budget_remaining = max(budget_cap_cents - cost_cents, 0)

    return RunProgressSummary(
        run_id=run_id,
        phase=phase,
        last_tool=last_tool,
        next_action=next_action,
        elapsed_seconds=_elapsed_seconds(started_at, now=now),
        budget_remaining_cents=budget_remaining,
        budget_cap_cents=budget_cap_cents,
        cost_cents=cost_cents,
        iteration=iteration,
    )


def format_run_progress_summary(summary: RunProgressSummary) -> str:
    elapsed = (
        f'{summary.elapsed_seconds:.0f}s'
        if summary.elapsed_seconds is not None
        else 'unknown'
    )
    budget = 'unlimited'
    if summary.budget_cap_cents is not None:
        remaining = summary.budget_remaining_cents or 0
        budget = f'{remaining}c remaining of {summary.budget_cap_cents}c cap'
    lines = [
        f'Run progress: {summary.run_id}',
        f'Phase: {summary.phase}',
        f'Last tool: {summary.last_tool or "(none yet)"}',
        f'Next: {summary.next_action}',
        f'Elapsed: {elapsed}',
        f'Budget: {budget}',
        f'Cost so far: {summary.cost_cents}c',
    ]
    if summary.iteration is not None:
        lines.append(f'Iteration: {summary.iteration}')
    return '\n'.join(lines)
