from __future__ import annotations

import contextlib
import hashlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.storage import append_jsonl_line

_GENESIS_HASH = 'genesis'

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
SENSITIVE_STRING_PATTERNS = (
    (re.compile(r'\bBearer\s+[A-Za-z0-9._~+/=-]{8,}'), 'Bearer [redacted]'),
    (re.compile(r'\bsk-[A-Za-z0-9][A-Za-z0-9_-]{8,}\b'), AUDIT_REDACTED),
    (
        re.compile(r'(?i)\b(api[_-]?key|token|secret|password)=([^\s&;]{4,})'),
        r'\1=[redacted]',
    ),
    (
        re.compile(r'\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b'),
        '[redacted-JWT]',
    ),
    (
        re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        AUDIT_REDACTED,
    ),
    (
        re.compile(r'\b(ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
        AUDIT_REDACTED,
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)

    def to_json(
        self,
        *,
        prev_hash: Optional[str] = None,
        event_hash: Optional[str] = None,
    ) -> str:
        data: dict[str, Any] = {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'run_id': self.run_id,
            'created_at': self.created_at,
            'payload': self.payload,
        }
        if prev_hash is not None:
            data['prev_hash'] = prev_hash
            data['hash'] = event_hash or ''
        return json.dumps(data, sort_keys=True)


class AuditLogger:
    """Append-only audit logger with optional JSONL persistence."""

    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        redaction_config: Optional[Any] = None,
    ) -> None:
        self.path = path
        self.events: list[AuditEvent] = []
        self._sinks: list[Callable[[AuditEvent], None]] = []
        self._lock = threading.Lock()
        self._prev_hash: str = _GENESIS_HASH
        self._string_patterns = (
            redaction_config.build_patterns()
            if redaction_config is not None
            else SENSITIVE_STRING_PATTERNS
        )
        self._disk_error: Optional[OSError] = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            secure_audit_dir(self.path.parent)

    @property
    def disk_error(self) -> Optional[OSError]:
        """Returns the first ``OSError`` that disabled disk writes, or ``None``."""
        return self._disk_error

    def add_sink(self, sink: Callable[[AuditEvent], None]) -> None:
        self._sinks.append(sink)

    def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            run_id=run_id,
            payload=redact_audit_payload(
                payload, string_patterns=self._string_patterns
            ),
        )
        with self._lock:
            self.events.append(event)
            if self.path is not None and self._disk_error is None:
                prev = self._prev_hash
                canonical = json.dumps(
                    {
                        'event_id': event.event_id,
                        'event_type': event.event_type,
                        'run_id': event.run_id,
                        'created_at': event.created_at,
                        'payload': event.payload,
                        'prev_hash': prev,
                    },
                    sort_keys=True,
                    separators=(',', ':'),
                )
                current_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
                try:
                    append_jsonl_line(
                        self.path,
                        event.to_json(prev_hash=prev, event_hash=current_hash),
                    )
                    self._prev_hash = current_hash
                    secure_audit_file(self.path)
                except OSError as exc:
                    self._disk_error = exc
                    err_event = AuditEvent(
                        event_type='_disk_write_error',
                        run_id=event.run_id,
                        payload={'error': str(exc), 'errno': exc.errno},
                    )
                    self.events.append(err_event)
            sinks = list(self._sinks)
        for sink in sinks:
            with contextlib.suppress(Exception):
                sink(event)
        return event


def redact_audit_payload(
    payload: dict[str, Any],
    *,
    string_patterns: Any = None,
) -> dict[str, Any]:
    patterns = (
        string_patterns if string_patterns is not None else SENSITIVE_STRING_PATTERNS
    )
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == 'arguments' and isinstance(value, dict):
            redacted[key] = redact_tool_arguments(value, string_patterns=patterns)
        elif key == 'result' and isinstance(value, dict):
            redacted[key] = redact_tool_result(value, string_patterns=patterns)
        else:
            redacted[key] = redact_audit_value(key, value, string_patterns=patterns)
    return redacted


def secure_audit_dir(path: Path) -> None:
    path.chmod(AUDIT_DIR_MODE)


def secure_audit_file(path: Path) -> None:
    path.chmod(AUDIT_FILE_MODE)


def redact_tool_arguments(
    arguments: dict[str, Any], *, string_patterns: Any = None
) -> dict[str, Any]:
    return {
        str(key): redact_tool_argument_value(
            str(key), value, string_patterns=string_patterns
        )
        for key, value in arguments.items()
    }


def redact_tool_argument_value(
    key: str, value: Any, *, string_patterns: Any = None
) -> Any:
    if is_sensitive_key(key) or key in SENSITIVE_ARGUMENT_KEYS:
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_tool_argument_value(
                str(child_key), child_value, string_patterns=string_patterns
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            redact_tool_argument_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            redact_tool_argument_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    return redact_audit_value(key, value, string_patterns=string_patterns)


def redact_tool_result(
    result: dict[str, Any], *, string_patterns: Any = None
) -> dict[str, Any]:
    return {
        str(key): redact_tool_result_value(
            str(key), value, string_patterns=string_patterns
        )
        for key, value in result.items()
    }


def redact_tool_result_value(
    key: str, value: Any, *, string_patterns: Any = None
) -> Any:
    if is_sensitive_key(key) or key in SENSITIVE_RESULT_KEYS:
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_tool_result_value(
                str(child_key), child_value, string_patterns=string_patterns
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            redact_tool_result_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            redact_tool_result_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    return redact_audit_value(key, value, string_patterns=string_patterns)


def redact_audit_value(key: str, value: Any, *, string_patterns: Any = None) -> Any:
    # Only redact string / bytes values by key sensitivity.
    # Numeric, bool, and None values are telemetry data and are never sensitive.
    if is_sensitive_key(key) and isinstance(value, (str, bytes)):
        return AUDIT_REDACTED
    if isinstance(value, dict):
        return {
            str(child_key): redact_audit_value(
                str(child_key), child_value, string_patterns=string_patterns
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            redact_audit_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            redact_audit_value('', item, string_patterns=string_patterns)
            for item in value
        ]
    if isinstance(value, str):
        patterns = (
            string_patterns
            if string_patterns is not None
            else SENSITIVE_STRING_PATTERNS
        )
        redacted = redact_sensitive_string(value, patterns=patterns)
        if len(redacted) > MAX_AUDIT_STRING_LENGTH:
            return redacted[:MAX_AUDIT_STRING_LENGTH] + AUDIT_TRUNCATED
        return redacted
    return value


def redact_sensitive_string(value: str, *, patterns: Any = None) -> str:
    active = patterns if patterns is not None else SENSITIVE_STRING_PATTERNS
    redacted = value
    for pattern, replacement in active:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace('-', '_')
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
