"""Audit log hash-chain verification with tampering detection.

Each event persisted by ``AuditLogger`` carries two extra fields:

``prev_hash``
    SHA-256 hex digest of the *previous* event's canonical JSON, or the
    sentinel string ``"genesis"`` for the very first event.

``hash``
    SHA-256 hex digest of *this* event's canonical JSON (which includes
    ``prev_hash``).

``chain_hmac``
    Optional HMAC-SHA256 signature over ``hash``, keyed with a per-run
    secret.  Provided when the caller supplied ``secret_key``.

``verify_audit_chain`` reads a JSONL audit log and confirms that every
chained event's hash is correct, the ``prev_hash`` chain is unbroken,
and timestamps are monotonically non-decreasing.  All failures are
collected and reported, not just the first one.

Tampering indicators detected:
- **Hash mismatch** — event content was modified after recording
- **prev_hash mismatch** — events were inserted, deleted, or reordered
- **Timestamp regression** — events are out of chronological order
- **Missing chain fields** — legacy or tampered events without hashes
- **HMAC mismatch** — signature does not match the per-run secret key

Legacy log lines that lack ``prev_hash`` / ``hash`` fields are skipped
and the chain is reset at that point (backward compatibility).
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import blake3 as _blake3

    _BLAKE3_AVAILABLE = True
except ImportError:
    _blake3 = None
    _BLAKE3_AVAILABLE = False

logger = logging.getLogger(__name__)

GENESIS_HASH = 'genesis'

_CHAIN_FIELDS = frozenset(
    {'event_id', 'event_type', 'run_id', 'created_at', 'payload', 'prev_hash'}
)

# Hash algorithm selection (SHA-256 by default; Blake3 when available and opted in).
_hash_algorithm: str = 'sha256'


def set_hash_algorithm(algo: str) -> None:
    """Set the hash algorithm used for audit chain integrity.

    Args:
        algo: ``'sha256'`` (default) or ``'blake3'`` (must be installed).
    """
    global _hash_algorithm
    if algo not in ('sha256', 'blake3'):
        raise ValueError(f'unsupported hash algorithm: {algo!r}')
    if algo == 'blake3' and not _BLAKE3_AVAILABLE:
        raise ImportError('Blake3 is not installed. Install with: pip install blake3')
    _hash_algorithm = algo


def _hash_bytes(data: bytes) -> bytes:
    """Compute the configured hash of *data*."""
    if _hash_algorithm == 'blake3' and _BLAKE3_AVAILABLE:
        return _blake3.blake3(data).digest()
    return hashlib.sha256(data).digest()


def _hash_hex(data: bytes) -> str:
    """Compute the configured hash of *data*, returning a hex string."""
    if _hash_algorithm == 'blake3' and _BLAKE3_AVAILABLE:
        return _blake3.blake3(data).hexdigest()
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class ChainFailure:
    """A single integrity failure detected during chain verification."""

    line_number: int
    """1-based line number in the audit log file."""

    event_number: int
    """0-based event index (skipping non-event lines)."""

    category: str
    """Failure category: hash_mismatch, prev_hash_mismatch, timestamp_regression,
    missing_fields, hmac_mismatch, json_parse_error."""

    message: str
    """Human-readable description of the failure."""

    severity: str = 'error'
    """Severity: error (integrity violation), warning (non-critical anomaly)."""


@dataclass(frozen=True)
class ChainVerificationResult:
    """Outcome of :func:`verify_audit_chain`.

    When ``valid`` is False, ``failures`` contains every detected problem.
    ``error`` retains the first failure message for backward compatibility.
    """

    valid: bool
    event_count: int
    error: Optional[str] = None
    failures: list[ChainFailure] = field(default_factory=list)
    total_hash_mismatches: int = 0
    total_prev_hash_mismatches: int = 0
    total_timestamp_regressions: int = 0
    total_legacy_events: int = 0


def compute_event_hash(obj: dict) -> str:
    """Return the hex digest for *obj* using canonical field ordering and the
    configured hash algorithm (SHA-256 by default, Blake3 optional).

    Only the six chain fields are included so that non-chain metadata
    added by external tools does not invalidate the hash.
    """
    canonical = json.dumps(
        {
            'event_id': obj['event_id'],
            'event_type': obj['event_type'],
            'run_id': obj['run_id'],
            'created_at': obj['created_at'],
            'payload': obj['payload'],
            'prev_hash': obj['prev_hash'],
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return _hash_hex(canonical.encode('utf-8'))


def compute_chain_hmac(event_hash: str, secret_key: bytes) -> str:
    """Return the HMAC-SHA256 hex digest for *event_hash* keyed with *secret_key*.

    This binds each audit event to the per-run secret so that an attacker
    who can write the audit file cannot forge the chain without the key.
    """
    return hmac.HMAC(secret_key, event_hash.encode('utf-8'), hashlib.sha256).hexdigest()


def _verify_single_event(
    obj: dict,
    prev_hash: str,
    line_index: int,
    secret_key: bytes | None,
    strict: bool,
    allow_legacy_reset: bool,
) -> tuple[str | None, list[ChainFailure]]:
    """Verify a single event. Returns (next_prev_hash, failures)."""
    failures: list[ChainFailure] = []

    if 'prev_hash' not in obj or 'hash' not in obj:
        if strict and not allow_legacy_reset:
            failures.append(
                ChainFailure(
                    line_number=line_index,
                    event_number=-1,
                    category='missing_fields',
                    message=(
                        f'Line {line_index}: legacy event without chain fields '
                        'rejected in strict audit-chain mode'
                    ),
                    severity='error',
                )
            )
            return None, failures
        logger.warning(
            'Line %d: legacy event without chain fields — '
            'hash chain anchor reset to genesis; '
            'chain integrity cannot be verified across this boundary',
            line_index,
        )
        return GENESIS_HASH, failures

    stored_prev = obj['prev_hash']
    if stored_prev != prev_hash:
        failures.append(
            ChainFailure(
                line_number=line_index,
                event_number=-1,
                category='prev_hash_mismatch',
                message=(
                    f'Line {line_index}: prev_hash mismatch '
                    f'(expected {prev_hash!r}, got {stored_prev!r})'
                ),
                severity='error',
            )
        )

    try:
        expected = compute_event_hash(obj)
    except KeyError as exc:
        failures.append(
            ChainFailure(
                line_number=line_index,
                event_number=-1,
                category='missing_fields',
                message=f'Line {line_index}: missing required field {exc}',
                severity='error',
            )
        )
        return None, failures

    if obj['hash'] != expected:
        failures.append(
            ChainFailure(
                line_number=line_index,
                event_number=-1,
                category='hash_mismatch',
                message=(
                    f'Line {line_index}: hash mismatch for event '
                    f'{obj.get("event_id", "?")} — content may have been tampered'
                ),
                severity='error',
            )
        )

    if secret_key is not None and 'chain_hmac' in obj:
        expected_hmac = compute_chain_hmac(obj['hash'], secret_key)
        if obj['chain_hmac'] != expected_hmac:
            failures.append(
                ChainFailure(
                    line_number=line_index,
                    event_number=-1,
                    category='hmac_mismatch',
                    message=(
                        f'Line {line_index}: HMAC mismatch for event '
                        f'{obj.get("event_id", "?")} — signature does not match key'
                    ),
                    severity='error',
                )
            )

    return obj['hash'], failures


def _parse_timestamp(value: object) -> Optional[datetime]:
    """Parse a timestamp from an audit event. Returns None if unparseable."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        for fmt in (
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
        ):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None


def verify_audit_chain(  # noqa: C901
    log_path: Path,
    secret_key: Optional[bytes] = None,
    *,
    strict: Optional[bool] = None,
    allow_legacy_reset: Optional[bool] = None,
) -> ChainVerificationResult:
    from teaagent.security_env import (
        audit_chain_legacy_compat,
        audit_chain_strict,
    )

    if strict is None:
        strict = audit_chain_strict()
    if allow_legacy_reset is None:
        allow_legacy_reset = audit_chain_legacy_compat()
    if secret_key is None:
        secret_key = _load_run_key(log_path)

    if not log_path.is_file():
        return ChainVerificationResult(valid=True, event_count=0)

    text = log_path.read_text(encoding='utf-8').strip()
    if not text:
        return ChainVerificationResult(valid=True, event_count=0)

    lines = text.splitlines()
    prev_hash: str = GENESIS_HASH
    last_timestamp: Optional[datetime] = None
    all_failures: list[ChainFailure] = []
    event_idx = 0
    total_hash_mismatches = 0
    total_prev_hash_mismatches = 0
    total_timestamp_regressions = 0
    total_legacy_events = 0

    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            all_failures.append(
                ChainFailure(
                    line_number=i + 1,
                    event_number=event_idx,
                    category='json_parse_error',
                    message=f'Line {i + 1}: invalid JSON: {exc}',
                    severity='error',
                )
            )
            event_idx += 1
            return ChainVerificationResult(
                valid=False,
                event_count=event_idx,
                error=all_failures[0].message,
                failures=all_failures,
                total_hash_mismatches=total_hash_mismatches,
                total_prev_hash_mismatches=total_prev_hash_mismatches,
                total_timestamp_regressions=total_timestamp_regressions,
                total_legacy_events=total_legacy_events,
            )

        event_idx += 1

        new_prev, failures = _verify_single_event(
            obj, prev_hash, i + 1, secret_key, strict, allow_legacy_reset
        )

        # Annotate failures with correct event_number
        for f in failures:
            all_failures.append(
                ChainFailure(
                    line_number=f.line_number,
                    event_number=event_idx,
                    category=f.category,
                    message=f.message,
                    severity=f.severity,
                )
            )

        # Count failure types
        for f in failures:
            if f.category == 'hash_mismatch':
                total_hash_mismatches += 1
            elif f.category == 'prev_hash_mismatch':
                total_prev_hash_mismatches += 1

        # Check timestamp ordering
        created_at = obj.get('created_at')
        if created_at is not None:
            current_ts = _parse_timestamp(created_at)
            if (
                current_ts is not None
                and last_timestamp is not None
                and current_ts < last_timestamp
            ):
                total_timestamp_regressions += 1
                all_failures.append(
                    ChainFailure(
                        line_number=i + 1,
                        event_number=event_idx,
                        category='timestamp_regression',
                        message=(
                            f'Line {i + 1}: timestamp regression for event '
                            f'{obj.get("event_id", "?")} — '
                            f'{created_at} is earlier than previous event '
                            f'({last_timestamp.isoformat()})'
                        ),
                        severity='warning',
                    )
                )
            if current_ts is not None:
                last_timestamp = current_ts

        # Track legacy events
        if 'prev_hash' not in obj or 'hash' not in obj:
            total_legacy_events += 1

        # Continue chain even after failures (use expected hash for chain)
        # so we can detect cascading vs isolated issues
        if new_prev is not None:
            prev_hash = new_prev
        else:
            # On hash failure, compute expected hash to keep chain going
            with contextlib.suppress(KeyError, TypeError):
                prev_hash = compute_event_hash({**obj, 'prev_hash': prev_hash})

    valid = len(all_failures) == 0
    first_error = all_failures[0].message if all_failures else None

    return ChainVerificationResult(
        valid=valid,
        event_count=event_idx,
        error=first_error,
        failures=all_failures,
        total_hash_mismatches=total_hash_mismatches,
        total_prev_hash_mismatches=total_prev_hash_mismatches,
        total_timestamp_regressions=total_timestamp_regressions,
        total_legacy_events=total_legacy_events,
    )


def _load_run_key(log_path: Path) -> bytes | None:
    run_id = log_path.stem
    safe_id = ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'
    key_path = Path.home() / '.teaagent' / 'run-keys' / f'{safe_id}.key'
    if not key_path.is_file():
        return None
    try:
        key = key_path.read_bytes()
        if len(key) == 32:
            return key
    except OSError as exc:
        logger.warning(
            'HMAC chain key could not be read from %s: %s — '
            'proceeding without chain integrity verification',
            key_path,
            exc,
        )
    return None


def last_chain_hash(log_path: Path) -> str:
    """Return the hash to use as ``prev_hash`` when appending to an existing log."""
    if not log_path.is_file():
        return GENESIS_HASH

    _TAIL_SIZE = 4096
    try:
        file_size = log_path.stat().st_size
        if file_size == 0:
            return GENESIS_HASH
        with log_path.open('rb') as f:
            f.seek(max(0, file_size - _TAIL_SIZE))
            tail = f.read().decode('utf-8', errors='replace')
    except OSError:
        return GENESIS_HASH

    for raw_line in reversed(tail.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if 'prev_hash' not in obj or 'hash' not in obj:
            return GENESIS_HASH
        if isinstance(obj.get('hash'), str) and obj['hash']:
            return obj['hash']
        return GENESIS_HASH

    if file_size > _TAIL_SIZE:
        return _last_chain_hash_full(log_path)
    return GENESIS_HASH


def read_audit_events(log_path: Path) -> list[dict]:
    """Read all audit events from a JSONL file, skipping malformed lines.

    Returns a list of parsed event dicts in file order.  Non-dict lines
    are silently skipped.
    """
    if not log_path.is_file():
        return []
    events: list[dict] = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _last_chain_hash_full(log_path: Path) -> str:
    last_hash = GENESIS_HASH
    for line in log_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if 'prev_hash' not in obj or 'hash' not in obj:
            last_hash = GENESIS_HASH
            continue
        if isinstance(obj.get('hash'), str) and obj['hash']:
            last_hash = obj['hash']
    return last_hash
