"""Test module for background run lifecycle and notification.

This module tests the background run system, which enables long-running agent
tasks to execute asynchronously. The system supports starting, listing, monitoring,
and receiving notifications for background runs.

Key concepts tested:
- Background Start: BackgroundRunStore starts processes with metadata
- Background List: BackgroundRunStore lists all background processes
- Process Monitoring: Background processes are monitored for completion
- Session Streaming: stream_run_events streams audit events for a run
- Desktop Notification: --notify flag triggers desktop notifications on completion
- Attach Integration: agent attach --notify triggers notifications

Acceptance Criteria:
- AC1: BackgroundRunStore.start() creates a background process record
- AC2: BackgroundRunStore.list() returns all background processes
- AC3: BackgroundRunStore.get() returns process status including alive flag
- AC4: stream_run_events streams audit events for a completed run
- AC5: agent attach --notify triggers desktop notification on completion
- AC6: agent attach --follow --notify triggers notification on completion

Technical Details:
- BackgroundRunStore manages .teaagent/background/*.json files
- Each background record includes: background_id, pid, command, started_at, log_path
- Process monitoring checks if process is alive via _process_exists
- stream_run_events reads audit log and yields events
- Desktop notifications use platform-specific notify functions
- Notifications include run_id and status in the message

References:
- Background run design: /docs/architecture/background_runs.md
- Session streaming: /docs/specs/session_streaming.md
"""

from __future__ import annotations

import io
import json
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


def test_background_attach_with_notify_triggers_desktop_notification(
    tmp_path: Path,
) -> None:
    run_id = 'bg-notify-run'
    store = RunStore(tmp_path)
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task='notify test')
    audit.record('heartbeat', run_id, tick=1, interval_seconds=0.1)
    audit.record('run_completed', run_id, answer='done')

    with patch('teaagent.ergonomics.notify.notify') as mock_notify:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                ['agent', 'attach', run_id, '--notify', '--root', str(tmp_path)]
            )

        assert code == 0
        mock_notify.assert_called_once_with('TeaAgent', 'Run bg-notify-run: completed')

        payload = json.loads(out.getvalue())
        assert payload['run_id'] == run_id
        assert payload['run_state']['status'] == 'completed'


def test_background_attach_follow_with_notify(tmp_path: Path) -> None:
    run_id = 'bg-follow-notify-run'
    store = RunStore(tmp_path)
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task='follow notify test')
    audit.record('heartbeat', run_id, tick=1, interval_seconds=0.1)
    audit.record('run_completed', run_id, answer='done')

    with patch('teaagent.ergonomics.notify.notify') as mock_notify:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    'agent',
                    'attach',
                    run_id,
                    '--follow',
                    '--notify',
                    '--root',
                    str(tmp_path),
                ]
            )

        assert code == 0
        mock_notify.assert_called_once_with(
            'TeaAgent', 'Run bg-follow-notify-run: completed'
        )
