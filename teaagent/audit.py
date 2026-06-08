"""Append-only audit logging with tiered levels and redaction."""

from __future__ import annotations

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

from teaagent.errors import AuditDurabilityError
from teaagent.storage import file_lock

try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

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

    def __init__(  # noqa: C901
        self,
        path: Optional[Path] = None,
        *,
        redaction_config: Optional[Any] = None,
        audit_level: AuditLevel = 'L2',  # Default to redacted payload level
        encryption_key: Optional[bytes] = None,
        compliance_mode: Optional[bool] = None,
    ) -> None:
        from teaagent.security_env import compliance_mode as env_compliance_mode

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
        self._consecutive_disk_failures: int = 0
        self._disk_error_cooldown_seconds: float = 30.0
        self._compliance_mode = (
            env_compliance_mode() if compliance_mode is None else compliance_mode
        )
        self._chain_key = self._load_or_save_chain_key()
        self._audit_level = audit_level
        self._file_chmod_done = False  # Track if chmod has been done
        self._last_timestamp_str: Optional[str] = None

        # Encryption setup for L3 audit logs
        self._encryption_key: Optional[bytes] = encryption_key
        self._fernet: Optional[Any] = None
        if audit_level == 'L3':
            if not CRYPTO_AVAILABLE:
                raise AuditDurabilityError(
                    'L3 audit level requires cryptography library',
                    hint='Install the cryptography library with: pip install cryptography',
                )
            if self._encryption_key is None:
                # Generate a new encryption key if not provided
                self._encryption_key = self._load_or_save_encryption_key()
            try:
                if self._encryption_key is None:
                    raise ValueError('Encryption key is required')
                self._fernet = Fernet(self._encryption_key)
            except Exception as exc:
                raise AuditDurabilityError(
                    f'Failed to initialize L3 encryption: {exc}',
                    hint='Check that the encryption key is valid and the cryptography library is installed.',
                ) from exc

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
                                    self._last_timestamp_str = last_entry.get(
                                        'created_at'
                                    )
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
            except OSError as exc:
                logger.warning(
                    'HMAC chain key could not be read from %s: %s — '
                    'generating new key; chain will not be reproducible across restarts',
                    key_path,
                    exc,
                )
        key = os.urandom(32)
        try:
            key_dir.mkdir(parents=True, exist_ok=True)
            key_dir.chmod(0o700)
            key_path.write_bytes(key)
            key_path.chmod(0o600)
        except OSError as exc:
            logger.warning(
                'HMAC chain key could not be persisted to %s: %s — '
                'audit chain will be non-reproducible across restarts',
                key_path,
                exc,
            )
        return key

    def _load_or_save_encryption_key(self) -> bytes:
        """Load or generate encryption key for L3 audit logs."""
        if self.path is None:
            return Fernet.generate_key()

        run_id = self.path.stem
        safe_id = (
            ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'
        )
        key_dir = Path.home() / '.teaagent' / 'audit-encryption'
        key_path = key_dir / f'{safe_id}.enc'

        if key_path.is_file():
            try:
                key = key_path.read_bytes()
                if len(key) == 44:  # Fernet key length
                    return key
            except OSError as exc:
                raise AuditDurabilityError(
                    f'Failed to load encryption key from {key_path}: {exc}',
                    hint='Verify the encryption key file exists and is readable.',
                ) from exc

        key = Fernet.generate_key()
        try:
            key_dir.mkdir(parents=True, exist_ok=True)
            key_dir.chmod(0o700)
            key_path.write_bytes(key)
            key_path.chmod(0o600)
        except OSError as exc:
            raise AuditDurabilityError(
                f'Failed to save encryption key to {key_path}: {exc}',
                hint='Ensure the directory ~/.teaagent/audit-encryption/ is writable.',
            ) from exc
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
            - Encryption at rest is implemented using Fernet (AES-128 in CBC mode).
            - Note: Key is stored on the same host (~/.teaagent/audit-encryption/), so this protects
              against log file copying but not host/user compromise.
            - Encrypted logs can be decrypted using AuditLogger.decrypt_audit_log() for post-mortem analysis.
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
            # Encryption is applied when writing to disk in the record() method
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

    def record(self, event_type: str, run_id: str, **payload: Any) -> AuditEvent:  # noqa: C901
        # Apply tiered audit level filtering
        filtered_payload = self._apply_audit_level(payload)

        # For L3, skip redaction (full trace) but apply encryption at rest
        if self._audit_level == 'L3':
            event_payload = filtered_payload
        else:
            event_payload = redact_audit_payload(
                filtered_payload, string_patterns=self._string_patterns
            )

        event_id = uuid4().hex
        created_at = utc_now()

        with self._lock:
            path = self.path

        if path is not None and self.disk_error is None:
            from teaagent.audit_chain import _hash_hex, compute_chain_hmac

            try:
                with file_lock(path):
                    # Enforce monotonicity under file lock
                    created_at = utc_now()
                    if (
                        self._last_timestamp_str
                        and created_at < self._last_timestamp_str
                    ):
                        created_at = self._last_timestamp_str
                    self._last_timestamp_str = created_at

                    prev = self._prev_hash

                    # Encrypt payload for L3
                    payload_to_write = event_payload
                    if self._audit_level == 'L3':
                        # Encryption is required for L3 - fail closed if it fails
                        if self._fernet is None:
                            raise AuditDurabilityError(
                                'L3 encryption not initialized',
                                hint="Reinitialize AuditLogger with audit_level='L3' to set up encryption.",
                            )
                        try:
                            payload_json = json.dumps(event_payload, sort_keys=True)
                            encrypted_bytes = self._fernet.encrypt(
                                payload_json.encode('utf-8')
                            )
                            payload_to_write = {
                                'encrypted': encrypted_bytes.decode('utf-8')
                            }
                        except Exception as exc:
                            raise AuditDurabilityError(
                                f'L3 encryption failed: {exc}',
                                hint='Verify the payload can be serialized to JSON and the encryption key is valid.',
                            ) from exc

                    canonical = json.dumps(
                        {
                            'event_id': event_id,
                            'event_type': event_type,
                            'run_id': run_id,
                            'created_at': created_at,
                            'payload': payload_to_write,
                            'prev_hash': prev,
                        },
                        sort_keys=True,
                        separators=(',', ':'),
                    )
                    current_hash = _hash_hex(canonical.encode('utf-8'))
                    chain_hmac = compute_chain_hmac(current_hash, self._chain_key)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('a', encoding='utf-8') as handle:
                        # Write the canonical form directly to ensure hash matches what's written
                        entry_data = json.loads(canonical)
                        entry_data['hash'] = current_hash
                        entry_data['chain_hmac'] = chain_hmac
                        handle.write(
                            json.dumps(entry_data, sort_keys=True).rstrip('\n') + '\n'
                        )
                        handle.flush()
                        os.fsync(handle.fileno())
                    # Only chmod once at file creation
                    if not self._file_chmod_done:
                        secure_audit_file(path)
                        self._file_chmod_done = True

                    # Update _prev_hash before releasing file_lock to prevent race
                    # Atomic string assignment doesn't need self._lock
                    self._prev_hash = current_hash

                with self._lock:
                    self._disk_error = None
                    self._last_disk_error_time = 0.0
                    self._consecutive_disk_failures = 0
            except OSError as exc:
                with self._lock:
                    self._disk_error = exc
                    self._last_disk_error_time = time.monotonic()
                    self._consecutive_disk_failures += 1
                    err_event = AuditEvent(
                        event_type='_disk_write_error',
                        run_id=run_id,
                        payload={'error': str(exc), 'errno': exc.errno},
                    )
                    self.events.append(err_event)
                if self._compliance_mode:
                    raise AuditDurabilityError(
                        f'Audit disk write failed: {exc}',
                        cause=exc,
                    ) from exc
                if self._consecutive_disk_failures >= 3:
                    import sys

                    print(
                        f'AUDIT CRITICAL: {self._consecutive_disk_failures} consecutive '
                        f'disk write failures — audit integrity degraded. '
                        f'Halting run.',
                        file=sys.stderr,
                    )

                    raise AuditDurabilityError(
                        f'{self._consecutive_disk_failures} consecutive disk write failures',
                    ) from None
                logger.warning(
                    'Audit disk write failed: %s (errno=%s) — '
                    'run continues in memory-only mode. '
                    'Enable compliance mode for fatal audit durability enforcement.',
                    exc,
                    exc.errno,
                    extra={
                        'event': 'audit_disk_write_failed',
                        'error_code': 'AUDIT_DISK_WRITE',
                    },
                )
        else:
            with self._lock:
                if self._last_timestamp_str and created_at < self._last_timestamp_str:
                    created_at = self._last_timestamp_str
                self._last_timestamp_str = created_at

        event = AuditEvent(
            event_type=event_type,
            run_id=run_id,
            payload=event_payload,
            event_id=event_id,
            created_at=created_at,
        )

        with self._lock:
            self.events.append(event)
            sinks = list(self._sinks)

        failed_sinks = []
        for sink in sinks:
            try:
                sink(event)
            except Exception as exc:
                logger.error(
                    f'Audit sink {sink.__class__.__name__} failed: {exc}',
                    exc_info=True,
                    extra={
                        'event': 'audit_sink_failed',
                        'error_code': 'AUDIT_SINK_ERROR',
                    },
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
            from teaagent.audit_chain import _hash_hex

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
                computed_hash = _hash_hex(canonical.encode('utf-8'))

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

    @staticmethod
    def _load_encryption_key(
        audit_path: Path, encryption_key: Optional[bytes] = None
    ) -> bytes:
        if encryption_key is not None:
            return encryption_key
        run_id = audit_path.stem
        safe_id = (
            ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'
        )
        key_dir = Path.home() / '.teaagent' / 'audit-encryption'
        key_path = key_dir / f'{safe_id}.enc'
        if not key_path.is_file():
            raise AuditDurabilityError(
                f'Encryption key not found at {key_path}',
                hint='Ensure the key file exists at the specified path for this run.',
            )
        try:
            key = key_path.read_bytes()
        except OSError as exc:
            raise AuditDurabilityError(
                f'Failed to load encryption key from {key_path}: {exc}',
                hint='Check file permissions for the encryption key file.',
            ) from exc
        if len(key) != 44:
            raise AuditDurabilityError(
                f'Invalid encryption key length at {key_path}',
                hint='The encryption key file is corrupted; regenerate it.',
            )
        return key

    @staticmethod
    @staticmethod
    def _verify_raw_chain(raw_events: list[dict[str, Any]]) -> list[str]:
        from teaagent.audit_chain import _hash_hex

        chain_errors = []
        prev_hash = _GENESIS_HASH
        for i, event in enumerate(raw_events):
            event_hash = event.get('hash')
            event_prev_hash = event.get('prev_hash')
            if event_prev_hash != prev_hash:
                chain_errors.append(
                    f'Event {i}: prev_hash mismatch (expected {prev_hash}, got {event_prev_hash})'
                )
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
            computed_hash = _hash_hex(canonical.encode('utf-8'))
            if event_hash != computed_hash:
                chain_errors.append(
                    f'Event {i}: hash mismatch (expected {computed_hash}, got {event_hash})'
                )
            prev_hash = event_hash or computed_hash
        return chain_errors

    @staticmethod
    @staticmethod
    def _decrypt_events(
        raw_events: list[dict[str, Any]], fernet: Any
    ) -> list[dict[str, Any]]:
        decrypted_events = []
        for event in raw_events:
            payload = event.get('payload', {})
            if isinstance(payload, dict) and 'encrypted' in payload:
                try:
                    encrypted_data = payload['encrypted']
                    decrypted_bytes = fernet.decrypt(encrypted_data.encode('utf-8'))
                    decrypted_json = decrypted_bytes.decode('utf-8')
                    event['payload'] = json.loads(decrypted_json)
                except Exception as exc:
                    raise AuditDurabilityError(
                        f'Failed to decrypt event {event.get("event_id")}: {exc}',
                        hint='The audit log may be corrupted or the encryption key may have changed.',
                    ) from exc
            decrypted_events.append(event)
        return decrypted_events

    @staticmethod
    def decrypt_audit_log(
        audit_path: Path, encryption_key: Optional[bytes] = None
    ) -> dict[str, Any]:
        if not CRYPTO_AVAILABLE:
            raise AuditDurabilityError(
                'Decryption requires the cryptography library',
                hint='Install the cryptography library with: pip install cryptography',
            )

        encryption_key = AuditLogger._load_encryption_key(audit_path, encryption_key)

        try:
            fernet = Fernet(encryption_key)
        except Exception as exc:
            raise AuditDurabilityError(
                f'Failed to initialize Fernet with provided key: {exc}',
                hint='The provided encryption key is invalid or malformed.',
            ) from exc

        try:
            lines = audit_path.read_text(encoding='utf-8').splitlines()
            raw_events = [json.loads(line) for line in lines if line.strip()]

            chain_errors = AuditLogger._verify_raw_chain(raw_events)
            decrypted_events = AuditLogger._decrypt_events(raw_events, fernet)

            return {
                'events': decrypted_events,
                'chain_valid': len(chain_errors) == 0,
                'chain_errors': chain_errors,
                'total_events': len(decrypted_events),
            }
        except OSError as exc:
            raise AuditDurabilityError(
                f'Failed to read audit log from {audit_path}: {exc}',
                hint='Check that the audit log file exists and is readable.',
            ) from exc
        except json.JSONDecodeError as exc:
            raise AuditDurabilityError(
                f'Failed to parse audit log JSON: {exc}',
                hint='The audit log file may be corrupted or not in valid JSONL format.',
            ) from exc


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
