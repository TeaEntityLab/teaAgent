from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional, TextIO

from teaagent.audit import AuditEvent


@dataclass(frozen=True)
class StreamEvent:
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type, **self.payload}


def emit_stream_event(
    event: StreamEvent | dict[str, Any],
    *,
    out: TextIO | None = None,
) -> None:
    stream = out or sys.stdout
    if isinstance(event, StreamEvent):
        payload = event.to_dict()
    else:
        payload = event
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True), file=stream, flush=True
    )


def audit_dict_to_stream_event(raw: dict[str, Any]) -> Optional[StreamEvent]:
    event_type = str(raw.get('event_type', ''))
    if not event_type:
        return None
    payload = raw.get('payload')
    if not isinstance(payload, dict):
        payload = {
            key: value
            for key, value in raw.items()
            if key
            not in (
                'event_type',
                'run_id',
                'event_id',
                'created_at',
                'prev_hash',
                'event_hash',
            )
        }
    return audit_event_to_stream_event(
        AuditEvent(
            event_type=event_type,
            run_id=str(raw.get('run_id', '')),
            payload=payload,
        )
    )


def audit_event_to_stream_event(event: AuditEvent) -> Optional[StreamEvent]:
    payload = event.payload or {}
    if event.event_type == 'iteration_started':
        return StreamEvent('iteration_started', {'iteration': payload.get('iteration')})
    if event.event_type == 'tool_call_started':
        return StreamEvent(
            'tool_call_started',
            {
                'tool_name': payload.get('tool_name'),
                'call_id': payload.get('call_id'),
            },
        )
    if event.event_type == 'tool_call_completed':
        return StreamEvent(
            'tool_call_completed',
            {'tool_name': payload.get('tool_name'), 'call_id': payload.get('call_id')},
        )
    if event.event_type == 'tool_call_failed':
        return StreamEvent(
            'tool_call_failed',
            {
                'tool_name': payload.get('tool_name'),
                'call_id': payload.get('call_id'),
                'error': payload.get('error'),
            },
        )
    if event.event_type == 'run_failed':
        return StreamEvent(
            'run_failed',
            {
                'category': payload.get('category'),
                'message': payload.get('message'),
            },
        )
    if event.event_type == 'run_completed':
        return StreamEvent('run_completed', {'run_id': payload.get('run_id')})
    if event.event_type == 'approval_required':
        return StreamEvent('approval_required', dict(payload))
    return None


def format_progress_line(event: AuditEvent) -> Optional[str]:
    mapped = audit_event_to_stream_event(event)
    if mapped is None:
        return None
    if mapped.type == 'iteration_started':
        return f'  iter {mapped.payload.get("iteration")}'
    if mapped.type == 'tool_call_started':
        return (
            f'  tool: {mapped.payload.get("tool_name")} '
            f'({mapped.payload.get("call_id")})'
        )
    if mapped.type == 'tool_call_completed':
        return f'  tool ok: {mapped.payload.get("tool_name")}'
    if mapped.type == 'run_failed':
        return (
            f'  failed: {mapped.payload.get("category")}: '
            f'{mapped.payload.get("message")}'
        )
    return None


def audit_sink_for_json_stream(
    emit: Callable[[StreamEvent], None],
) -> Callable[[AuditEvent], None]:
    def _sink(event: AuditEvent) -> None:
        mapped = audit_event_to_stream_event(event)
        if mapped is not None:
            emit(mapped)

    return _sink


def audit_sink_for_progress(
    stderr: TextIO | None = None,
) -> Callable[[AuditEvent], None]:
    stream = stderr or sys.stderr

    def _sink(event: AuditEvent) -> None:
        line = format_progress_line(event)
        if line:
            print(line, file=stream, flush=True)

    return _sink
