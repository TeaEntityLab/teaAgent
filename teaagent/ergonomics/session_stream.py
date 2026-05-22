from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterator, Optional

from teaagent.run_store import RunStore


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            import json

            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _is_terminal(events: list[dict[str, Any]]) -> bool:
    terminal = {'run_completed', 'run_failed'}
    return any(event.get('event_type') in terminal for event in events)


def stream_run_events(
    run_id: str,
    *,
    root: str | Path = '.',
    follow: bool = False,
    poll_interval: float = 0.5,
    max_wait: Optional[float] = None,
) -> Iterator[dict[str, Any]]:
    """Yield audit events for a run, optionally tailing until completion."""
    store = RunStore(root)
    path = store.run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"run '{run_id}' not found")
    seen = 0
    deadline = time.monotonic() + max_wait if max_wait is not None else None
    while True:
        events = _load_events(path)
        for event in events[seen:]:
            yield event
        seen = len(events)
        status = store.heartbeat_for_run(run_id).get('status')
        if events and _is_terminal(events):
            return
        if not follow:
            return
        if status not in ('running', 'unknown'):
            return
        if deadline is not None and time.monotonic() >= deadline:
            return
        time.sleep(poll_interval)
