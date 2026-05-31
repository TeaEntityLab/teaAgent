from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from teaagent.budget import RunBudget


def _unique_strs(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _changed_paths_from_undo_journal(path: Path) -> list[str]:
    if not path.is_file():
        return []
    paths: list[str] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        p = obj.get('path')
        if isinstance(p, str) and p:
            paths.append(p)
    return _unique_strs(paths)


def summarize_run(
    *,
    root: str | Path,
    run_id: str,
    events: list[dict[str, Any]],
    cost_cents: float,
    input_tokens: int,
    output_tokens: int,
    budget_cap_cents: Optional[int] = None,
) -> dict[str, Any]:
    if not isinstance(events, list):
        events = []
    try:
        cost_cents_value = float(cost_cents)
    except (TypeError, ValueError):
        cost_cents_value = 0.0
    try:
        input_tokens_value = int(input_tokens)
    except (TypeError, ValueError):
        input_tokens_value = 0
    try:
        output_tokens_value = int(output_tokens)
    except (TypeError, ValueError):
        output_tokens_value = 0

    tool_calls_total = 0
    read_calls = 0
    write_calls = 0
    for event in events:
        if event.get('event_type') != 'tool_call_started':
            continue
        tool_calls_total += 1
        payload = event.get('payload', {})
        if not isinstance(payload, dict):
            payload = {}
        annotations = payload.get('annotations', {})
        if not isinstance(annotations, dict):
            annotations = {}
        if annotations.get('read_only'):
            read_calls += 1
        else:
            write_calls += 1

    resolved_root = Path(root).resolve()
    undo_path = resolved_root / '.teaagent' / 'undo' / f'{run_id}.jsonl'
    changed_paths = _changed_paths_from_undo_journal(undo_path)

    if budget_cap_cents is None:
        budget_cap_cents = RunBudget().max_estimated_cost_cents
    remaining_cents = float(budget_cap_cents) - float(cost_cents_value)

    summary: dict[str, Any] = {
        'tool_calls_total': tool_calls_total,
        'tool_calls_read': read_calls,
        'tool_calls_write': write_calls,
        'files_changed': changed_paths,
        'files_changed_count': len(changed_paths),
        'cost_usd': cost_cents_value / 100.0,
        'budget_cap_usd': budget_cap_cents / 100.0,
        'budget_remaining_usd': max(0.0, remaining_cents / 100.0),
        'audit_log': f'.teaagent/runs/{run_id}.jsonl',
        'undo_command': f'teaagent agent undo {run_id}',
        'input_tokens': input_tokens_value,
        'output_tokens': output_tokens_value,
    }
    return summary


def format_run_summary(summary: dict[str, Any]) -> str:
    tool_calls = summary.get('tool_calls_total', 0)
    tool_read = summary.get('tool_calls_read', 0)
    tool_write = summary.get('tool_calls_write', 0)
    files_changed = summary.get('files_changed_count', 0)
    cost = summary.get('cost_usd', 0.0)
    cap = summary.get('budget_cap_usd')
    remaining = summary.get('budget_remaining_usd')
    audit_log = summary.get('audit_log', '')
    undo_cmd = summary.get('undo_command', '')
    cap_str = (
        f'  Budget remaining: ${remaining:.2f} / ${cap:.2f}\n'
        if isinstance(cap, (int, float)) and isinstance(remaining, (int, float))
        else ''
    )
    return (
        'Run summary:\n'
        f'  Tools called:     {tool_calls} ({tool_read} read, {tool_write} write)\n'
        f'  Files changed:    {files_changed}\n'
        f'  Cost:             ${cost:.2f}\n'
        f'{cap_str}'
        f'  Audit log:        {audit_log}\n'
        f'  Undo:             {undo_cmd}\n'
    )
