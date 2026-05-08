from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from teaagent.audit import AuditEvent, utc_now


@dataclass(frozen=True)
class TraceSpan:
    name: str
    run_id: str
    span_id: str
    started_at: str
    ended_at: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)


class TraceRecorder:
    """Small audit-event sink that can be replaced by OpenTelemetry later."""

    def __init__(self) -> None:
        self.spans: list[TraceSpan] = []
        self._open_tool_spans: dict[str, TraceSpan] = {}

    def handle_event(self, event: AuditEvent) -> None:
        if event.event_type == 'run_started':
            self.spans.append(
                TraceSpan(
                    name='agent.run',
                    run_id=event.run_id,
                    span_id=event.event_id,
                    started_at=event.created_at,
                    attributes={'task': event.payload.get('task')},
                )
            )
            return

        if event.event_type == 'tool_call_started':
            call_id = event.payload['call_id']
            span = TraceSpan(
                name='tool.call',
                run_id=event.run_id,
                span_id=call_id,
                started_at=event.created_at,
                attributes={
                    'tool_name': event.payload.get('tool_name'),
                    'annotations': event.payload.get('annotations', {}),
                },
            )
            self._open_tool_spans[call_id] = span
            self.spans.append(span)
            return

        if event.event_type == 'tool_call_completed':
            call_id = event.payload['call_id']
            open_span = self._open_tool_spans.pop(call_id, None)
            if open_span is not None:
                self._replace_span(open_span, ended_at=event.created_at)
            return

        if event.event_type in {'run_completed', 'run_failed'}:
            self.spans.append(
                TraceSpan(
                    name=event.event_type,
                    run_id=event.run_id,
                    span_id=event.event_id,
                    started_at=event.created_at,
                    ended_at=utc_now(),
                    attributes=event.payload,
                )
            )

    def _replace_span(self, original: TraceSpan, *, ended_at: str) -> None:
        for index, span in enumerate(self.spans):
            if span.span_id == original.span_id:
                self.spans[index] = TraceSpan(
                    name=span.name,
                    run_id=span.run_id,
                    span_id=span.span_id,
                    started_at=span.started_at,
                    ended_at=ended_at,
                    attributes=span.attributes,
                )
                return
