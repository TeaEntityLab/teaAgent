from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from teaagent.storage import file_lock

try:
    from teaagent.telemetry import TelemetryConfig, configure_telemetry

    _OPENTELEMETRY_AVAILABLE = True
except ImportError:
    _OPENTELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)

_GENESIS_HASH = 'genesis'

AUDIT_REDACTED = '[redacted]'
AUDIT_TRUNCATED = '[truncated]'

# Audit level tiers for tiered logging
AuditLevel = Literal['L0', 'L1', 'L2', 'L3']
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
        chain_hmac: Optional[str] = None,
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
            if chain_hmac is not None:
                data['chain_hmac'] = chain_hmac
        return json.dumps(data, sort_keys=True)


class AuditLogger:
    """Append-only audit logger with optional JSONL persistence and tiered audit levels."""

    def __init__(
        self,
        path: Optional[Path] = None,
        *,
        redaction_config: Optional[Any] = None,
        audit_level: AuditLevel = 'L2',  # Default to redacted payload level
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
        self._last_disk_error_time: float = 0.0
        self._disk_error_cooldown_seconds: float = 30.0
        self._chain_key = self._load_or_save_chain_key()
        self._audit_level = audit_level
        self._file_chmod_done = False  # Track if chmod has been done
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            secure_audit_dir(self.path.parent)
            if self.path.is_file() and self.path.stat().st_size > 0:
                try:
                    with open(self.path) as f:
                        lines = f.readlines()
                    for line in reversed(lines):
                        line = line.strip()
                        if line:
                            try:
                                last_entry = json.loads(line)
                                if 'hash' in last_entry:
                                    self._prev_hash = last_entry['hash']
                                    break
                            except json.JSONDecodeError:
                                continue
                except (OSError, json.JSONDecodeError):
                    pass

    @property
    def disk_error(self) -> Optional[OSError]:
        """Returns the most recent ``OSError`` if still within cooldown, or ``None``.

        A transient error causes a 30-second cooldown (default), not permanent
        silence.  After the cooldown expires disk writes are retried.
        """
        if (
            self._disk_error is not None
            and time.monotonic() - self._last_disk_error_time
            < self._disk_error_cooldown_seconds
        ):
            return self._disk_error
        return None

    def _load_or_save_chain_key(self) -> bytes:
        if self.path is None:
            return os.urandom(32)
        run_id = self.path.stem
        # Inline safe_run_id to avoid circular imports
        safe_id = (
            ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'
        )
        key_dir = Path.home() / '.teaagent' / 'run-keys'
        key_path = key_dir / f'{safe_id}.key'
        if key_path.is_file():
            try:
                key = key_path.read_bytes()
                if len(key) == 32:
                    return key
            except OSError:
                pass
        key = os.urandom(32)
        try:
            key_dir.mkdir(parents=True, exist_ok=True)
            key_dir.chmod(0o700)
            key_path.write_bytes(key)
            key_path.chmod(0o600)
        except OSError:
            pass
        return key

    def get_chain_key(self) -> bytes:
        """Return the per-run HMAC secret key for external chain verification."""
        return self._chain_key

    def _apply_audit_level(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply tiered audit level filtering to payload.

        L0: Metrics only (minimal metadata)
            - Keeps: event_type, timestamp
            - Removes: all other fields

        L1: Metadata (event types, timestamps, no arguments)
            - Keeps: event_type, timestamp, and other metadata
            - Removes: arguments, result, content, output, input

        L2: Redacted payload (default, sensitive data redacted)
            - Returns payload as-is (redaction handled by redact_audit_payload)

        L3: Full local trace (all data, no redaction)
            - Returns payload as-is with no additional filtering.
            - Encryption at rest is NOT implemented; payloads are stored in plaintext.
        """
        if self._audit_level == 'L0':
            # Only keep basic metrics
            return {
                'event_type': payload.get('event_type'),
                'timestamp': payload.get('timestamp'),
            }
        elif self._audit_level == 'L1':
            # Keep metadata but remove detailed arguments/results
            filtered = dict(payload)
            # Remove sensitive detailed fields
            for key in [
                'arguments',
                'result',
                'content',
                'output',
                'input',
                'reasoning',
            ]:
                filtered.pop(key, None)
            return filtered
        elif self._audit_level == 'L2':
            # Default redacted payload (already handled by redact_audit_payload)
            return payload
        elif self._audit_level == 'L3':
            # Full trace - no additional filtering
            return payload
        else:
            # Default to L2 behavior
            return payload

    def add_sink(self, sink: Callable[[AuditEvent], None]) -> None:
        self._sinks.append(sink)

    def enable_opentelemetry(
        self,
        *,
        endpoint: Optional[str] = None,
        service_name: str = 'teaagent',
        service_version: str = '1.0.0',
    ) -> None:
        """Enable OpenTelemetry export for audit events.

        Args:
            endpoint: OpenTelemetry endpoint (e.g., "http://localhost:4317")
            service_name: Service name for telemetry
            service_version: Service version for telemetry
        """
        if not _OPENTELEMETRY_AVAILABLE:
            logger.warning(
                'OpenTelemetry not available - install opentelemetry-api and opentelemetry-sdk'
            )
            return

        try:
            config = TelemetryConfig(
                otlp_endpoint=endpoint,
                service_name=service_name,
                service_version=service_version,
            )
            otel_sink_tuple = configure_telemetry(config)
            otel_sink = otel_sink_tuple[0]  # Extract just the sink

            # Wrap the sink's handle_event method as a callable
            def otel_wrapper(event: AuditEvent) -> None:
                otel_sink.handle_event(event)

            self.add_sink(otel_wrapper)
            logger.info(f'OpenTelemetry sink added: {endpoint}')
        except Exception as e:
            logger.error(f'Failed to enable OpenTelemetry: {e}')

    def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent:
        # Apply tiered audit level filtering
        filtered_payload = self._apply_audit_level(payload)

        event = AuditEvent(
            event_type=event_type,
            run_id=run_id,
            payload=redact_audit_payload(
                filtered_payload, string_patterns=self._string_patterns
            ),
        )
        # SAFETY: self._lock and file_lock must never be held simultaneously (deadlock).
        with self._lock:
            self.events.append(event)
            path = self.path
            sinks = list(self._sinks)

        if path is not None and self.disk_error is None:
            from teaagent.audit_chain import compute_chain_hmac

            try:
                with file_lock(path):
                    # Use in-memory _prev_hash instead of disk read for performance
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
                    chain_hmac = compute_chain_hmac(current_hash, self._chain_key)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('a', encoding='utf-8') as handle:
                        handle.write(
                            event.to_json(
                                prev_hash=prev,
                                event_hash=current_hash,
                                chain_hmac=chain_hmac,
                            ).rstrip('\n')
                            + '\n'
                        )
                        handle.flush()
                        os.fsync(handle.fileno())
                    # Only chmod once at file creation
                    if not self._file_chmod_done:
                        secure_audit_file(path)
                        self._file_chmod_done = True
                with self._lock:
                    self._prev_hash = current_hash
                    self._disk_error = None
                    self._last_disk_error_time = 0.0
            except OSError as exc:
                with self._lock:
                    self._disk_error = exc
                    self._last_disk_error_time = time.monotonic()
                    err_event = AuditEvent(
                        event_type='_disk_write_error',
                        run_id=event.run_id,
                        payload={'error': str(exc), 'errno': exc.errno},
                    )
                    self.events.append(err_event)
        failed_sinks = []
        for sink in sinks:
            try:
                sink(event)
            except Exception as exc:
                logger.error(
                    f'Audit sink {sink.__class__.__name__} failed: {exc}', exc_info=True
                )
                failed_sinks.append((sink, exc))

        if failed_sinks:
            logger.warning(f'{len(failed_sinks)} audit sink(s) failed')
        return event

    def verify_chain_integrity(self) -> dict[str, Any]:
        """Verify the hash chain integrity of the audit log.

        Returns:
            Dict with 'valid' (bool), 'total_events' (int), and 'errors' (list[str])
        """
        if not self.path or not self.path.is_file():
            return {
                'valid': False,
                'total_events': 0,
                'errors': ['No audit file found'],
            }

        try:
            lines = self.path.read_text(encoding='utf-8').splitlines()
            events = []
            for line in lines:
                if line.strip():
                    events.append(json.loads(line))

            if not events:
                return {'valid': True, 'total_events': 0, 'errors': []}

            errors = []
            prev_hash = _GENESIS_HASH
            for i, event in enumerate(events):
                event_hash = event.get('hash')
                event_prev_hash = event.get('prev_hash')

                if event_prev_hash != prev_hash:
                    errors.append(
                        f'Event {i}: prev_hash mismatch (expected {prev_hash}, got {event_prev_hash})'
                    )

                # Verify the hash matches the content
                canonical = json.dumps(
                    {
                        'event_id': event.get('event_id'),
                        'event_type': event.get('event_type'),
                        'run_id': event.get('run_id'),
                        'created_at': event.get('created_at'),
                        'payload': event.get('payload'),
                        'prev_hash': event_prev_hash,
                    },
                    sort_keys=True,
                    separators=(',', ':'),
                )
                computed_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

                if event_hash != computed_hash:
                    errors.append(
                        f'Event {i}: hash mismatch (expected {computed_hash}, got {event_hash})'
                    )

                prev_hash = event_hash or computed_hash

            return {
                'valid': len(errors) == 0,
                'total_events': len(events),
                'errors': errors,
            }
        except Exception as exc:
            return {
                'valid': False,
                'total_events': 0,
                'errors': [f'Verification failed: {exc}'],
            }


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
    # Skip redaction for primitive types (optimization)
    if value is None or isinstance(value, (int, float, bool)):
        return value
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
    # Skip redaction for primitive types (optimization)
    if value is None or isinstance(value, (int, float, bool)):
        return value
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
