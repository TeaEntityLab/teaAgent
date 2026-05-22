from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from teaagent.ergonomics.file_tail import iter_jsonl_tail


def test_iter_jsonl_tail_follows_appended_lines() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'events.jsonl'
        path.write_text(
            json.dumps({'event_type': 'iteration_started', 'n': 1}) + '\n',
            encoding='utf-8',
        )
        seen: list[dict] = []

        def _consume() -> None:
            for event in iter_jsonl_tail(
                path,
                follow=True,
                poll_interval=0.05,
                use_inotify=False,
                stop_when=lambda: len(seen) >= 2,
            ):
                seen.append(event)

        thread = threading.Thread(target=_consume, daemon=True)
        thread.start()
        time.sleep(0.1)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event_type': 'run_completed', 'n': 2}) + '\n')
            handle.flush()
        thread.join(timeout=3)
        assert len(seen) >= 2
        assert seen[0]['event_type'] == 'iteration_started'
        assert seen[-1]['event_type'] == 'run_completed'
