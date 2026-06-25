"""Shared RunStore test fixtures for writing audit events on disk."""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.run_store import RunStore


def write_run_events(root: str | Path, run_id: str, events: list[dict]) -> Path:
    """Persist *events* as JSONL for *run_id* under *root*."""
    store = RunStore(root)
    run_path = store.run_path(run_id)
    lines = '\n'.join(json.dumps(event, sort_keys=True) for event in events) + '\n'
    run_path.write_text(lines, encoding='utf-8')
    return run_path


def write_undo_journal(root: str | Path, run_id: str) -> Path:
    """Create a minimal undo journal file for *run_id*."""
    store = RunStore(root)
    undo_path = store.undo_path(run_id)
    undo_path.parent.mkdir(parents=True, exist_ok=True)
    undo_path.write_text(json.dumps({'entry': 'fake'}) + '\n', encoding='utf-8')
    return undo_path
