"""Stable run event stream contract (WS5-002)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from teaagent.audit import redact_audit_payload
from teaagent.audit_tail import classify_audit_event


@dataclass(frozen=True)
class RunEvent:
    """Portable event record for CLI, TUI, tests, and remote consumers."""

    event_id: str
    run_id: str
    event_type: str
    created_at: str
    classification: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'run_id': self.run_id,
            'event_type': self.event_type,
            'created_at': self.created_at,
            'classification': self.classification,
            'payload': self.payload,
        }


@runtime_checkable
class RunEventSubscriber(Protocol):
    def on_event(self, event: RunEvent) -> None:
        """Receive one normalized run event."""


def _event_field(event: Any, name: str, default: Any = '') -> Any:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def normalize_run_event(event: Any) -> RunEvent:
    """Map internal audit records to the stable stream contract."""
    event_type = str(_event_field(event, 'event_type', ''))
    payload = _event_field(event, 'payload', {})
    if not isinstance(payload, dict):
        payload = {}
    return RunEvent(
        event_id=str(_event_field(event, 'event_id', '')),
        run_id=str(_event_field(event, 'run_id', '')),
        event_type=event_type,
        created_at=str(_event_field(event, 'created_at', '')),
        classification=classify_audit_event(event_type),
        payload=redact_audit_payload(payload),
    )


class RunEventStream:
    """In-process pub/sub over normalized run events."""

    def __init__(self) -> None:
        self._subscribers: list[RunEventSubscriber] = []

    def subscribe(self, subscriber: RunEventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def emit(self, raw_event: Any) -> RunEvent:
        event = normalize_run_event(raw_event)
        for subscriber in list(self._subscribers):
            subscriber.on_event(event)
        return event

    def replay(self, events: list[Any]) -> list[RunEvent]:
        return [self.emit(event) for event in events]


def replay_run_events(events: list[Any]) -> RunEventStream:
    """Replay audit events into a fresh stream (read-only consumers)."""
    stream = RunEventStream()
    stream.replay(events)
    return stream
