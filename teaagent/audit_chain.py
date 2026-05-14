"""Audit log hash-chain verification.

Each event persisted by ``AuditLogger`` carries two extra fields:

``prev_hash``
    SHA-256 hex digest of the *previous* event's canonical JSON, or the
    sentinel string ``"genesis"`` for the very first event.

``hash``
    SHA-256 hex digest of *this* event's canonical JSON (which includes
    ``prev_hash``).

``verify_audit_chain`` reads a JSONL audit log and confirms that every
chained event's hash is correct and that the ``prev_hash`` chain is
unbroken.  Any insertion, deletion, or content modification produces a
verification failure with an explanatory error string.

Legacy log lines that lack ``prev_hash`` / ``hash`` fields are skipped
and the chain is reset at that point (backward compatibility).
"""

from __future__ import annotations

import hashlib
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


def verify_audit_chain(log_path: Path) -> ChainVerificationResult:
    """Verify the SHA-256 hash chain of a JSONL audit log file.

    Returns :class:`ChainVerificationResult` with ``valid=True`` when
    every chained event is intact.  On failure the ``error`` field
    contains a human-readable description of the first violation found.
    """
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

        prev_hash = obj['hash']

    return ChainVerificationResult(valid=True, event_count=len(lines))
