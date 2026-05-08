from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from collections.abc import Callable
from typing import Any, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)

    def to_json(self) -> str:
        return json.dumps(
            {
                "event_id": self.event_id,
                "event_type": self.event_type,
                "run_id": self.run_id,
                "created_at": self.created_at,
                "payload": self.payload,
            },
            sort_keys=True,
        )


class AuditLogger:
    """Append-only audit logger with optional JSONL persistence."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self.events: list[AuditEvent] = []
        self._sinks: list[Callable[[AuditEvent], None]] = []
        self._lock = threading.Lock()
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def add_sink(self, sink: Callable[[AuditEvent], None]) -> None:
        self._sinks.append(sink)

    def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent:
        event = AuditEvent(event_type=event_type, run_id=run_id, payload=payload)
        with self._lock:
            self.events.append(event)
            if self.path is not None:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(event.to_json() + "\n")
            sinks = list(self._sinks)
        for sink in sinks:
            sink(event)
        return event
