from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

AUDIT_REDACTED = '[redacted]'
AUDIT_TRUNCATED = '[truncated]'
MAX_AUDIT_STRING_LENGTH = 20_000
AUDIT_DIR_MODE = 0o700
AUDIT_FILE_MODE = 0o600
SENSITIVE_KEY_PARTS = (
    'api_key',
    'authorization',
    'credential',
    'password',
    'secret',
    'token',
)
SENSITIVE_ARGUMENT_KEYS = frozenset({'command', 'content', 'new', 'old'})
SENSITIVE_RESULT_KEYS = frozenset({'content', 'stderr', 'stdout', 'text'})


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
                'event_id': self.event_id,
                'event_type': self.event_type,
                'run_id': self.run_id,
                'created_at': self.created_at,
                'payload': self.payload,
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
            secure_audit_dir(self.path.parent)

    def add_sink(self, sink: Callable[[AuditEvent], None]) -> None:
        self._sinks.append(sink)

    def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type, run_id=run_id, payload=redact_audit_payload(payload)
        )
        with self._lock:
            self.events.append(event)
            if self.path is not None:
                with self.path.open('a', encoding='utf-8') as handle:
                    handle.write(event.to_json() + '\n')
                secure_audit_file(self.path)
            sinks = list(self._sinks)
        for sink in sinks:
            sink(event)
        return event


def redact_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == 'arguments' and isinstance(value, dict):
            redacted[key] = redact_tool_arguments(value)
        elif key == 'result' and isinstance(value, dict):
            redacted[key] = redact_tool_result(value)
        else:
            redacted[key] = redact_audit_value(key, value)
    return redacted


def secure_audit_dir(path: Path) -> None:
    path.chmod(AUDIT_DIR_MODE)


def secure_audit_file(path: Path) -> None:
    path.chmod(AUDIT_FILE_MODE)


def redact_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): redact_tool_argument_value(str(key), value)
        for key, value in arguments.items()
    }


def redact_tool_argument_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key) or key in SENSITIVE_ARGUMENT_KEYS:
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_tool_argument_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_tool_argument_value('', item) for item in value]
    if isinstance(value, tuple):
        return [redact_tool_argument_value('', item) for item in value]
    return redact_audit_value(key, value)


def redact_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): redact_tool_result_value(str(key), value)
        for key, value in result.items()
    }


def redact_tool_result_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key) or key in SENSITIVE_RESULT_KEYS:
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_tool_result_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_tool_result_value('', item) for item in value]
    if isinstance(value, tuple):
        return [redact_tool_result_value('', item) for item in value]
    return redact_audit_value(key, value)


def redact_audit_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key):
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_audit_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_audit_value('', item) for item in value]
    if isinstance(value, tuple):
        return [redact_audit_value('', item) for item in value]
    if isinstance(value, str) and len(value) > MAX_AUDIT_STRING_LENGTH:
        return value[:MAX_AUDIT_STRING_LENGTH] + AUDIT_TRUNCATED
    return value


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace('-', '_')
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
