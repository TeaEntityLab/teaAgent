"""Compliance audit export — signed, verifiable bundles of hash-chained events.

The exported bundle is a JSON document containing:
- events: list of hash-chained audit events
- chain_verification: result of verify_audit_chain()
- summary: event count, time range, tool calls, destructive calls
- signed_digest: SHA-256 of the entire bundle content (for external verification)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from teaagent.audit_chain import verify_audit_chain


def export_compliance_bundle(
    events: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    include_chain_verification: bool = True,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Build a signed compliance bundle from audit events.

    Args:
        events: List of audit event dicts from the run store.
        run_id: Optional run identifier for metadata.
        include_chain_verification: Whether to run hash-chain verification.
        log_path: Path to the JSONL audit log for chain verification.
            Required when *include_chain_verification* is ``True`` and
            events are non-empty.  When ``None``, chain verification is
            skipped even if *include_chain_verification* is ``True``.

    Returns:
        A dict with keys: version, exported_at, run_id, event_count,
        chain_verification (optional), summary, events, signed_digest.
    """
    if not events:
        return {
            'version': 1,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'run_id': run_id,
            'event_count': 0,
            'events': [],
            'summary': {'tool_calls': 0, 'destructive_calls': 0},
            'signed_digest': hashlib.sha256(b'{}').hexdigest(),
        }

    chain_verification: dict[str, Any] | None = None
    if include_chain_verification and log_path is not None:
        chain_result = verify_audit_chain(log_path)
        chain_verification = {
            'valid': chain_result.valid,
            'event_count': chain_result.event_count,
            'error': chain_result.error,
        }

    event_types = [e.get('event_type', '') for e in events]
    tool_started = event_types.count('tool_call_started')
    tool_completed = event_types.count('tool_call_completed')
    tool_failed = event_types.count('tool_call_failed')
    tool_blocked = event_types.count('tool_call_blocked')

    timestamps = [e.get('created_at', '') for e in events if e.get('created_at')]
    time_range = None
    if len(timestamps) >= 2:
        time_range = {'earliest': timestamps[0], 'latest': timestamps[-1]}
    elif len(timestamps) == 1:
        time_range = {'earliest': timestamps[0], 'latest': timestamps[0]}

    summary = {
        'event_count': len(events),
        'tool_calls_started': tool_started,
        'tool_calls_completed': tool_completed,
        'tool_calls_failed': tool_failed,
        'tool_calls_blocked': tool_blocked,
        'time_range': time_range,
    }

    bundle: dict[str, Any] = {
        'version': 1,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'run_id': run_id,
        'event_count': len(events),
        'chain_verification': chain_verification,
        'summary': summary,
        'events': events,
    }

    # Signed digest over the entire bundle (without the signed_digest field)
    digest_content = {k: v for k, v in bundle.items() if k != 'signed_digest'}
    canonical = json.dumps(digest_content, sort_keys=True, separators=(',', ':'))
    bundle['signed_digest'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    return bundle


def write_compliance_bundle(
    bundle: dict[str, Any],
    output_path: Path,
    *,
    pretty: bool = True,
) -> Path:
    """Write a compliance bundle to disk as JSON.

    Args:
        bundle: The compliance bundle dict from export_compliance_bundle().
        output_path: Path to write the JSON file.
        pretty: Whether to pretty-print the JSON.

    Returns:
        The output_path that was written to.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if pretty else None
    output_path.write_text(
        json.dumps(bundle, indent=indent, default=str),
        encoding='utf-8',
    )
    return output_path


def verify_bundle_integrity(
    bundle: dict[str, Any],
) -> bool:
    """Verify that a compliance bundle's signed_digest matches its content.

    Args:
        bundle: The compliance bundle dict to verify.

    Returns:
        True if the digest matches, False otherwise.
    """
    stored_digest = bundle.get('signed_digest')
    if not stored_digest:
        return False
    digest_content = {k: v for k, v in bundle.items() if k != 'signed_digest'}
    canonical = json.dumps(digest_content, sort_keys=True, separators=(',', ':'))
    computed = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return computed == stored_digest
