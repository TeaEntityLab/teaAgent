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
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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
    return hmac.HMAC(secret_key, event_hash.encode('utf-8'), hashlib.sha256).hexdigest()


def _verify_single_event(
    obj: dict,
    prev_hash: str,
    line_index: int,
    secret_key: bytes | None,
    strict: bool,
    allow_legacy_reset: bool,
) -> tuple[str | None, str]:
    if 'prev_hash' not in obj or 'hash' not in obj:
        if strict and not allow_legacy_reset:
            return None, (
                f'Line {line_index}: legacy event without chain fields '
                'rejected in strict audit-chain mode'
            )
        logger.warning(
            'Line %d: legacy event without chain fields — '
            'hash chain anchor reset to genesis; '
            'chain integrity cannot be verified across this boundary',
            line_index,
        )
        return GENESIS_HASH, ''

    stored_prev = obj['prev_hash']
    if stored_prev != prev_hash:
        return None, (
            f'Line {line_index}: prev_hash mismatch '
            f'(expected {prev_hash!r}, got {stored_prev!r})'
        )

    try:
        expected = compute_event_hash(obj)
    except KeyError as exc:
        return None, f'Line {line_index}: missing required field {exc}'

    if obj['hash'] != expected:
        return None, (
            f'Line {line_index}: hash mismatch for event '
            f'{obj.get("event_id", "?")} — content may have been tampered'
        )

    if secret_key is not None and 'chain_hmac' in obj:
        expected_hmac = compute_chain_hmac(obj['hash'], secret_key)
        if obj['chain_hmac'] != expected_hmac:
            return None, (
                f'Line {line_index}: HMAC mismatch for event '
                f'{obj.get("event_id", "?")} — signature does not match key'
            )

    return obj['hash'], ''


def verify_audit_chain(
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

    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            return ChainVerificationResult(
                valid=False,
                event_count=i,
                error=f'Line {i + 1}: invalid JSON: {exc}',
            )

        new_prev, error = _verify_single_event(
            obj, prev_hash, i + 1, secret_key, strict, allow_legacy_reset
        )
        if error:
            return ChainVerificationResult(valid=False, event_count=i, error=error)
        prev_hash = new_prev if new_prev is not None else prev_hash

    return ChainVerificationResult(valid=True, event_count=len(lines))


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
