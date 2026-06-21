#!/usr/bin/env python3
"""G-P0-1: validate that AuditLogger events conform to the published schemas.

Standalone CI script (no pytest). Generates a small chained audit log via
``AuditLogger`` in a temp dir and validates every line against both the
logical event schema (``docs/audit-event.schema.json``) and the strict
chain-entry envelope (``docs/audit-chain-entry.schema.json``).

Exit codes:
    0 — all events conform to both schemas
    1 — one or more events failed validation
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENT_SCHEMA = REPO_ROOT / 'docs' / 'audit-event.schema.json'
CHAIN_ENTRY_SCHEMA = REPO_ROOT / 'docs' / 'audit-chain-entry.schema.json'


def _load_schema(path: Path) -> dict:
    if not path.is_file():
        print(f'ERROR: schema not found: {path}', file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding='utf-8'))


def _write_sample_chained_events(tmp_path: Path) -> Path:
    from teaagent.types import AuditLogger

    log_path = tmp_path / 'conformance.jsonl'
    with patch.object(Path, 'home', return_value=tmp_path):
        audit = AuditLogger(path=log_path)
        audit.record('run_started', 'r-conf', task='schema conformance CI check')
        audit.record('tool_call_completed', 'r-conf', tool_name='dummy', call_id='c1')
        audit.record('run_completed', 'r-conf', answer={'content': 'done'})
    return log_path


def _read_events(log_path: Path) -> list[dict]:
    events: list[dict] = []
    for line in log_path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def main() -> int:
    from jsonschema import Draft202012Validator

    event_schema = _load_schema(EVENT_SCHEMA)
    chain_schema = _load_schema(CHAIN_ENTRY_SCHEMA)

    with tempfile.TemporaryDirectory() as tmp:
        log_path = _write_sample_chained_events(Path(tmp))
        events = _read_events(log_path)

    if len(events) < 3:
        print(f'ERROR: expected >=3 events, got {len(events)}', file=sys.stderr)
        return 1

    event_validator = Draft202012Validator(event_schema)
    chain_validator = Draft202012Validator(chain_schema)

    failures: list[str] = []
    for event in events:
        for label, validator in (
            ('logical-event', event_validator),
            ('chain-entry', chain_validator),
        ):
            errors = sorted(validator.iter_errors(event), key=lambda e: e.message)
            if errors:
                for err in errors:
                    failures.append(
                        f'{label}: event {event.get("event_id")} — {err.message}'
                    )

    if failures:
        print(f'ERROR: {len(failures)} schema conformance failure(s):')
        for f in failures:
            print(f'  {f}')
        return 1

    print(
        f'OK: {len(events)} chained events conform to both schemas '
        f'(logical + chain-entry envelope).'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
