"""Audit log hash-chain verification.

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
chained event's hash is correct and that the ``prev_hash`` chain is
unbroken.  Any insertion, deletion, or content modification produces a
verification failure with an explanatory error string.

Legacy log lines that lack ``prev_hash`` / ``hash`` fields are skipped
and the chain is reset at that point (backward compatibility).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

GENESIS_HASH = 'genesis'

_CHAIN_FIELDS = frozenset(
    {'event_id', 'event_type', 'run_id', 'created_at', 'payload', 'prev_hash'}
)


@dataclass(frozen=True)
class ChainVerificationResult:
    """Outcome of :func:`verify_audit_chain`."""

    valid: bool
    event_count: int
    error: Optional[str] = None


def compute_event_hash(obj: dict) -> str:
    """Return the SHA-256 hex digest for *obj* using canonical field ordering.

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
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def compute_chain_hmac(event_hash: str, secret_key: bytes) -> str:
    """Return the HMAC-SHA256 hex digest for *event_hash* keyed with *secret_key*.

    This binds each audit event to the per-run secret so that an attacker
    who can write the audit file cannot forge the chain without the key.
    """
    return hmac.new(secret_key, event_hash.encode('utf-8'), hashlib.sha256).hexdigest()


def verify_audit_chain(
    log_path: Path,
    secret_key: Optional[bytes] = None,
) -> ChainVerificationResult:
    """Verify the SHA-256 hash chain of a JSONL audit log file.

    When *secret_key* is provided, also verifies the HMAC-SHA256 signature
    (``chain_hmac``) of every event that carries one.  Events written
    without HMAC (e.g. by an older version) are still accepted for
    backward compatibility.

    Returns :class:`ChainVerificationResult` with ``valid=True`` when
    every chained event is intact.  On failure the ``error`` field
    contains a human-readable description of the first violation found.
    """
    if secret_key is None:
        run_id = log_path.stem
        safe_id = (
            ''.join(ch for ch in run_id if ch.isalnum() or ch in {'-', '_'}) or 'run'
        )
        key_path = Path.home() / '.teaagent' / 'run-keys' / f'{safe_id}.key'
        if key_path.is_file():
            try:
                key = key_path.read_bytes()
                if len(key) == 32:
                    secret_key = key
            except OSError:
                pass

    if not log_path.is_file():
        return ChainVerificationResult(valid=True, event_count=0)

    text = log_path.read_text(encoding='utf-8').strip()
    if not text:
        return ChainVerificationResult(valid=True, event_count=0)

    lines = text.splitlines()
    prev_hash: str = GENESIS_HASH

    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            return ChainVerificationResult(
                valid=False,
                event_count=i,
                error=f'Line {i + 1}: invalid JSON: {exc}',
            )

        if 'prev_hash' not in obj or 'hash' not in obj:
            # Legacy event without chain fields — skip and reset chain origin.
            prev_hash = GENESIS_HASH
            continue

        stored_prev = obj['prev_hash']
        if stored_prev != prev_hash:
            return ChainVerificationResult(
                valid=False,
                event_count=i,
                error=(
                    f'Line {i + 1}: prev_hash mismatch '
                    f'(expected {prev_hash!r}, got {stored_prev!r})'
                ),
            )

        try:
            expected = compute_event_hash(obj)
        except KeyError as exc:
            return ChainVerificationResult(
                valid=False,
                event_count=i,
                error=f'Line {i + 1}: missing required field {exc}',
            )

        if obj['hash'] != expected:
            return ChainVerificationResult(
                valid=False,
                event_count=i,
                error=(
                    f'Line {i + 1}: hash mismatch for event '
                    f'{obj.get("event_id", "?")} — content may have been tampered'
                ),
            )

        # Verify HMAC when the event carries one and a key was provided.
        if secret_key is not None and 'chain_hmac' in obj:
            expected_hmac = compute_chain_hmac(obj['hash'], secret_key)
            if obj['chain_hmac'] != expected_hmac:
                return ChainVerificationResult(
                    valid=False,
                    event_count=i,
                    error=(
                        f'Line {i + 1}: HMAC mismatch for event '
                        f'{obj.get("event_id", "?")} — signature does not match key'
                    ),
                )

        prev_hash = obj['hash']

    return ChainVerificationResult(valid=True, event_count=len(lines))


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
