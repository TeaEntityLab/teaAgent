"""Formatted audit tail output with classification (WS4-004)."""

from __future__ import annotations

from typing import Any

from teaagent.audit import redact_audit_payload

_LIFECYCLE = frozenset(
    {'run_started', 'run_completed', 'run_failed', 'run_paused', 'iteration_started'}
)
_TOOL = frozenset(
    {
        'tool_call_started',
        'tool_call_completed',
        'tool_call_failed',
        'tool_call_blocked',
    }
)
_APPROVAL = frozenset(
    {
        'tool_call_pending_approval',
        'tool_call_approved',
        'tool_call_denied',
        'approval_granted',
        'approval_denied',
        'approval_requested',
    }
)
_AUDIT = frozenset({'_disk_write_error', 'context_compacted'})


def classify_audit_event(event_type: str) -> str:
    if event_type in _LIFECYCLE:
        return 'lifecycle'
    if event_type in _TOOL:
        return 'tool'
    if event_type in _APPROVAL:
        return 'approval'
    if event_type in _AUDIT:
        return 'audit'
    return 'other'


def tail_audit_events(
    events: list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    tail = events[-limit:] if limit > 0 else events
    formatted: list[dict[str, Any]] = []
    for event in tail:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get('event_type', ''))
        payload = event.get('payload')
        safe_payload = (
            redact_audit_payload(payload) if isinstance(payload, dict) else payload
        )
        formatted.append(
            {
                'created_at': event.get('created_at'),
                'event_type': event_type,
                'classification': classify_audit_event(event_type),
                'run_id': event.get('run_id'),
                'payload': safe_payload,
            }
        )
    return formatted


def format_audit_tail_human(events: list[dict[str, Any]], *, limit: int = 20) -> str:
    rows = tail_audit_events(events, limit=limit)
    if not rows:
        return 'No audit events.'
    lines = [f'Audit tail (last {len(rows)} events):', '']
    for row in rows:
        payload = row.get('payload')
        detail = ''
        if isinstance(payload, dict):
            tool = payload.get('tool_name')
            if tool:
                detail = f' tool={tool}'
            status = payload.get('status')
            if status:
                detail += f' status={status}'
        lines.append(
            f'[{row.get("classification")}] {row.get("created_at")} '
            f'{row.get("event_type")}{detail}'
        )
    return '\n'.join(lines)
