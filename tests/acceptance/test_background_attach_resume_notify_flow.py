"""Background runs: start, list, log run_id, stream events, notify hook."""

from __future__ import annotations

import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from teaagent.cli import main
from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.ergonomics.session_stream import stream_run_events
from teaagent.run_store import RunStore
from teaagent.runner import RunResult


def test_background_start_list_and_session_stream(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-bg-flow')
    audit.record('run_started', 'run-bg-flow', task='background smoke')
    audit.record('run_completed', 'run-bg-flow', answer='done')
    store.logger_for_result(
        RunResult(
            run_id='run-bg-flow',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )

    bg = BackgroundRunStore(tmp_path)
    record = bg.start(
        [
            sys.executable,
            '-c',
            "import json; print(json.dumps({'run_id':'run-bg-flow','status':'completed'}))",
        ],
        label='acceptance-bg',
    )
    rows = bg.list()
    assert any(row['background_id'] == record.background_id for row in rows)

    shown = bg.get(record.background_id)
    deadline = time.time() + 5.0
    while shown['alive'] and time.time() < deadline:
        time.sleep(0.05)
        shown = bg.get(record.background_id)
    assert shown['run_id'] == 'run-bg-flow'
    assert shown['alive'] is False
    assert shown['exit_code'] == 0

    events = list(stream_run_events('run-bg-flow', root=tmp_path))
    assert any(e.get('event_type') == 'run_completed' for e in events)


def test_agent_status_notify_flag_invokes_desktop_notify(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    audit = store.audit_logger('run-notify')
    audit.record('run_started', 'run-notify', task='notify me')
    audit.record('run_completed', 'run-notify', answer='ok')
    store.logger_for_result(
        RunResult(
            run_id='run-notify',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='completed',
        ),
        audit,
    )
    notified: list[tuple[str, str]] = []

    def _capture(title: str, message: str, *, sound: bool = False) -> bool:
        notified.append((title, message))
        return True

    out = io.StringIO()
    with (
        patch('teaagent.ergonomics.notify.notify', side_effect=_capture),
        redirect_stdout(out),
    ):
        code = main(
            [
                'agent',
                'attach',
                'run-notify',
                '--root',
                str(tmp_path),
                '--notify',
            ]
        )
    assert code == 0
    assert notified
    assert 'run-notify' in notified[0][1] or 'run-notify' in notified[0][0]
