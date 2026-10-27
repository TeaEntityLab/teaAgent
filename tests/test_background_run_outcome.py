# test-type: behavior
"""BG-001 §3.2 run outcome and §3.4 approval-flag forwarding for background runs."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pytest

from teaagent.ergonomics.background_run import (
    BackgroundRunStore,
    build_agent_run_command,
)

_DEAD_PID = 2_147_483_646
_DIGEST = 'a' * 64


def _write_record(
    store: BackgroundRunStore, background_id: str, **extra: object
) -> Path:
    log_path = store.dir / f'{background_id}.log'
    log_path.write_text('', encoding='utf-8')
    record: dict[str, object] = {
        'background_id': background_id,
        'pid': _DEAD_PID,
        'command': ['noop'],
        'started_at': '2026-10-01T00:00:00+00:00',
        'log_path': str(log_path),
    }
    record.update(extra)
    path = store.dir / f'{background_id}.json'
    path.write_text(json.dumps(record), encoding='utf-8')
    return path


def _write_audit(root: Path, run_id: str, events: list[dict[str, object]]) -> None:
    runs_dir = root / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({'run_id': run_id, 'timestamp': '2026-10-01T00:00:01+00:00', **ev})
        for ev in events
    ]
    (runs_dir / f'{run_id}.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def test_run_completed_outcome_is_completed(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-completed', run_id='run-completed')
    _write_audit(
        tmp_path,
        'run-completed',
        [{'event_type': 'run_completed', 'payload': {'answer': 'ok'}}],
    )

    rows = store.list()
    assert rows[0]['run_outcome'] == 'completed'
    assert store.get('bg-completed')['run_outcome'] == 'completed'


def test_run_failed_outcome_is_failed(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-failed', run_id='run-failed')
    _write_audit(
        tmp_path,
        'run-failed',
        [
            {
                'event_type': 'run_failed',
                'payload': {'category': 'model_logic', 'message': 'bad output'},
            }
        ],
    )

    assert store.get('bg-failed')['run_outcome'] == 'failed'


def test_cancelled_run_is_reported_as_cancelled_not_failed(tmp_path: Path) -> None:
    """RunCancelledError is recorded as run_failed; the outcome must still say cancelled."""
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-cancelled', run_id='run-cancelled')
    _write_audit(
        tmp_path,
        'run-cancelled',
        [
            {
                'event_type': 'run_failed',
                'payload': {
                    'category': 'system',
                    'message': 'run cancelled by cancel token',
                },
            }
        ],
    )

    assert store.get('bg-cancelled')['run_outcome'] == 'cancelled'


def test_paused_run_outcome_is_pending_approval(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-paused', run_id='run-paused')
    _write_audit(
        tmp_path,
        'run-paused',
        [{'event_type': 'run_paused', 'payload': {'status': 'pending_approval'}}],
    )

    assert store.get('bg-paused')['run_outcome'] == 'pending_approval'


def test_live_process_without_terminal_event_is_running(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    record = store.start(
        [sys.executable, '-c', 'import time; time.sleep(20)'], label='live'
    )
    store.update_run_id(record.background_id, 'run-still-going')
    try:
        shown = store.get(record.background_id)
        assert shown['alive'] is True
        assert shown['run_outcome'] == 'running'
    finally:
        store.stop(record.background_id, timeout_seconds=0.5)


def test_dead_process_without_terminal_event_is_unknown(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-no-terminal', run_id='run-no-terminal')

    shown = store.get('bg-no-terminal')
    assert shown['alive'] is False
    assert shown['run_outcome'] == 'unknown'


def test_record_without_run_id_is_unknown(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-no-run-id')

    rows = store.list()
    assert rows[0]['run_outcome'] == 'unknown'


def test_run_outcome_is_derived_and_never_persisted(tmp_path: Path) -> None:
    store = BackgroundRunStore(tmp_path)
    path = _write_record(store, 'bg-derived', run_id='run-derived')
    _write_audit(
        tmp_path,
        'run-derived',
        [{'event_type': 'run_completed', 'payload': {'answer': 'ok'}}],
    )

    store.get('bg-derived')
    store.list()
    store.stop('bg-derived', timeout_seconds=0.1)

    persisted = json.loads(path.read_text(encoding='utf-8'))
    assert 'run_outcome' not in persisted
    assert 'alive' not in persisted
    assert 'orphaned' not in persisted


def test_background_list_tty_table_shows_outcome_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from teaagent.cli._handlers._ergonomics import session as session_mod

    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-table', run_id='run-table')
    _write_audit(
        tmp_path,
        'run-table',
        [{'event_type': 'run_completed', 'payload': {'answer': 'ok'}}],
    )

    class _TTY(io.StringIO):
        def isatty(self) -> bool:
            return True

    fake_out = _TTY()
    monkeypatch.setattr(session_mod.sys, 'stdout', fake_out)
    rc = session_mod.background_list_command(argparse.Namespace(root=str(tmp_path)))

    assert rc == 0
    header_rows = [
        ln for ln in fake_out.getvalue().splitlines() if 'Background ID' in ln
    ]
    assert header_rows and 'Outcome' in header_rows[0]
    assert 'completed' in fake_out.getvalue()


def test_background_list_json_includes_run_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from teaagent.cli._handlers._ergonomics import session as session_mod

    store = BackgroundRunStore(tmp_path)
    _write_record(store, 'bg-json', run_id='run-json')
    _write_audit(
        tmp_path,
        'run-json',
        [{'event_type': 'run_failed', 'payload': {'message': 'boom'}}],
    )

    session_mod.background_list_command(argparse.Namespace(root=str(tmp_path)))
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]['run_outcome'] == 'failed'


def test_background_child_command_forwards_scoped_approvals() -> None:
    """§3.4: the approvals the parent supplied must reach the background child argv."""
    args = argparse.Namespace(
        provider='anthropic',
        root='/tmp/ws',
        allow_destructive=True,
        approve_call_id=[],
        approve_scoped=[f'write_file:{_DIGEST}', f'shell:{"b" * 64}'],
        hitl_approval=True,
        permission_mode='prompt',
    )
    cmd = build_agent_run_command(args, 'apply the patch')

    assert '--allow-destructive' in cmd
    assert '--hitl-approval' in cmd
    assert cmd[cmd.index('--permission-mode') + 1] == 'prompt'
    pairs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == '--approve-scoped']
    assert pairs == [f'write_file:{_DIGEST}', f'shell:{"b" * 64}']
