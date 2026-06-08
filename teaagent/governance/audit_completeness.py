"""Audit event completeness checks for run reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TOOL_LIFECYCLE = frozenset(
    {
        'tool_call_started',
        'tool_call_completed',
        'tool_call_failed',
        'tool_call_blocked',
        'tool_call_pending_approval',
        'tool_call_approved',
        'tool_call_denied',
    }
)


@dataclass
class AuditCompletenessReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    tool_calls: int = 0
    destructive_with_policy: int = 0


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get('payload')
    return payload if isinstance(payload, dict) else {}


def check_audit_completeness(events: list[dict[str, Any]]) -> AuditCompletenessReport:  # noqa: C901
    """Verify a run audit log supports basic accountability questions."""
    issues: list[str] = []
    if not events:
        return AuditCompletenessReport(ok=False, issues=['audit log is empty'])

    event_types = [e.get('event_type') for e in events]
    if event_types[0] != 'run_started':
        issues.append('first event must be run_started')
    if event_types[-1] not in {'run_completed', 'run_failed', 'run_paused'}:
        issues.append('final event must be run_completed, run_failed, or run_paused')

    run_ids = {e.get('run_id') for e in events}
    if len(run_ids) != 1 or None in run_ids:
        issues.append('all events must share one run_id')

    event_ids = [e.get('event_id') for e in events if e.get('event_id')]
    if len(event_ids) != len(set(event_ids)):
        issues.append('event_id values must be unique')

    tool_calls = 0
    destructive_with_policy = 0
    pending: dict[str, str] = {}

    for event in events:
        etype = event.get('event_type')
        payload = _event_payload(event)
        if etype == 'tool_call_started':
            tool_calls += 1
            call_id = payload.get('call_id')
            tool_name = payload.get('tool_name')
            if not isinstance(call_id, str) or not call_id:
                issues.append('tool_call_started missing call_id')
            if not isinstance(tool_name, str) or not tool_name:
                issues.append('tool_call_started missing tool_name')
            annotations = payload.get('annotations')
            if not isinstance(annotations, dict):
                issues.append('tool_call_started missing annotations')
            if isinstance(call_id, str) and call_id:
                pending[call_id] = tool_name or ''
        elif etype in _TOOL_LIFECYCLE - {'tool_call_started'}:
            call_id = payload.get('call_id')
            if isinstance(call_id, str) and call_id in pending:
                if etype in {
                    'tool_call_completed',
                    'tool_call_failed',
                    'tool_call_blocked',
                    'tool_call_denied',
                }:
                    pending.pop(call_id, None)
                if etype in {
                    'tool_call_blocked',
                    'tool_call_denied',
                    'tool_call_approved',
                }:
                    destructive_with_policy += 1

    for call_id in pending:
        issues.append(f'tool_call_started {call_id} has no terminal lifecycle event')

    return AuditCompletenessReport(
        ok=not issues,
        issues=issues,
        tool_calls=tool_calls,
        destructive_with_policy=destructive_with_policy,
    )
