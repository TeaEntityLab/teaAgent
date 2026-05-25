from __future__ import annotations

import pytest

from teaagent.ergonomics.session_stream import _is_terminal, stream_run_events
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_is_terminal_detects_completed_and_failed() -> None:
    assert _is_terminal([{'event_type': 'run_completed'}])
    assert _is_terminal([{'event_type': 'run_failed'}])
    assert not _is_terminal([{'event_type': 'run_started'}])


def test_stream_run_events_requires_existing_run_when_not_following(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        list(stream_run_events('missing-run', root=tmp_path, follow=False))


def test_stream_run_events_honors_max_wait(tmp_path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-wait')
    audit.record('run_started', 'run-wait', task='wait')
    store.logger_for_result(
        RunResult(
            run_id='run-wait',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    events = list(
        stream_run_events(
            'run-wait',
            root=tmp_path,
            follow=True,
            max_wait=0.01,
            poll_interval=0.01,
            use_inotify=False,
        )
    )
    assert any(event.get('event_type') == 'run_started' for event in events)
