"""Run inspection: trace timeline, export, dry-run replay."""

from __future__ import annotations

import json
from typing import Any

_TRACE_TYPES = frozenset(
    {
        'run_started',
        'iteration_started',
        'tool_call_pending_approval',
        'tool_call_approved',
        'tool_call_denied',
        'tool_call_blocked',
        'tool_call_started',
        'tool_call_completed',
        'tool_call_failed',
        'validation_started',
        'validation_finished',
        'run_completed',
        'run_failed',
        'run_paused',
        'undo_applied',
    }
)


def build_run_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a compact timeline suitable for CLI display."""
    trace: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_type = event.get('event_type')
        if event_type not in _TRACE_TYPES:
            continue
        raw_payload = event.get('payload')
        payload: dict[str, Any] = (
            raw_payload if isinstance(raw_payload, dict) else {}
        )
        entry: dict[str, Any] = {
            'index': index,
            'event_type': event_type,
            'created_at': event.get('created_at'),
            'event_id': event.get('event_id'),
        }
        if event_type.startswith('tool_call'):
            entry['tool_name'] = payload.get('tool_name')
            entry['call_id'] = payload.get('call_id')
            entry['status'] = event_type.removeprefix('tool_call_')
        if event_type == 'run_started':
            entry['task'] = payload.get('task')
        if event_type == 'run_completed':
            entry['status'] = payload.get('metadata', {}).get('status', 'completed')
        trace.append(entry)
    return trace


def export_run(events: list[dict[str, Any]], *, run_id: str) -> dict[str, Any]:
    """Export run metadata and events (already redacted on disk)."""
    from teaagent.governance.audit_completeness import check_audit_completeness

    completeness = check_audit_completeness(events)
    return {
        'run_id': run_id,
        'event_count': len(events),
        'trace': build_run_trace(events),
        'completeness': {
            'ok': completeness.ok,
            'issues': completeness.issues,
            'tool_calls': completeness.tool_calls,
        },
    }


def replay_dry_run(events: list[dict[str, Any]], *, run_id: str) -> dict[str, Any]:
    """Rebuild a decision chain without re-executing tools."""
    tools_used: list[str] = []
    approvals: list[dict[str, Any]] = []
    writes: list[str] = []

    for event in events:
        etype = event.get('event_type')
        raw_payload = event.get('payload')
        payload: dict[str, Any] = (
            raw_payload if isinstance(raw_payload, dict) else {}
        )
        tool_name = payload.get('tool_name')
        if etype == 'tool_call_completed' and isinstance(tool_name, str):
            tools_used.append(tool_name)
            if tool_name in {
                'workspace_write_file',
                'workspace_apply_patch',
                'workspace_edit_at_hash',
            }:
                path = payload.get('result', {}).get('path') or payload.get(
                    'arguments', {}
                ).get('path')
                if isinstance(path, str):
                    writes.append(path)
        if etype == 'tool_call_pending_approval':
            approvals.append(
                {
                    'call_id': payload.get('call_id'),
                    'tool_name': tool_name,
                }
            )

    return {
        'run_id': run_id,
        'mode': 'dry-run',
        'tools_used': tools_used,
        'write_paths': writes,
        'approval_requests': approvals,
        'trace': build_run_trace(events),
    }


def format_trace_text(trace: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in trace:
        etype = entry.get('event_type', '?')
        tool = entry.get('tool_name')
        suffix = f' ({tool})' if tool else ''
        lines.append(f'{entry.get("index", "?"):>3}  {etype}{suffix}')
    return '\n'.join(lines)


def dumps_export(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
