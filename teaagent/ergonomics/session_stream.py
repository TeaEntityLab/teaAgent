from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Iterator, Optional

from teaagent.ergonomics.file_tail import iter_jsonl_tail
from teaagent.run_store import RunStore


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
    use_inotify: bool = True,
) -> Iterator[dict[str, Any]]:
    """Yield audit events for a run, optionally tailing until completion."""
    store = RunStore(root)
    path = store.run_path(run_id)
    if not path.exists() and not follow:
        raise FileNotFoundError(f"run '{run_id}' not found")

    deadline = time.monotonic() + max_wait if max_wait is not None else None

    def _done() -> bool:
        if deadline is not None and time.monotonic() >= deadline:
            return True
        if not follow:
            return False
        status = store.heartbeat_for_run(run_id).get('status')
        return status not in ('running', 'unknown')

    seen_terminal = False
    for event in iter_jsonl_tail(
        path,
        follow=follow,
        poll_interval=poll_interval,
        stop_when=_done,
        use_inotify=use_inotify,
    ):
        yield event
        if event.get('event_type') in {'run_completed', 'run_failed'}:
            seen_terminal = True
            return

    if follow and not seen_terminal and path.exists():
        events = list(iter_jsonl_tail(path, follow=False, use_inotify=False))
        if events and _is_terminal(events):
            return
        status = store.heartbeat_for_run(run_id).get('status')
        if status not in ('running', 'unknown'):
            return
        if not path.exists():
            raise FileNotFoundError(f"run '{run_id}' not found")
