# test-type: behavior
"""Control cockpit surfaces detached background runs (running / orphaned)."""

from __future__ import annotations

import json
import logging
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.cockpit import build_control_cockpit
from teaagent.ergonomics.background_run import BackgroundRunStore
from teaagent.tui import TeaAgentTUI


def _render_cockpit(tui: TeaAgentTUI) -> str:
    buffer = StringIO()
    with (
        patch('sys.stdout', buffer),
        patch('shutil.get_terminal_size', return_value=(120, 30)),
    ):
        tui._print_state_panel()
    return buffer.getvalue()


def _seed_running_and_orphaned(root: Path) -> tuple[str, str]:
    """Create one live record and one dead record that has no clean exit."""
    store = BackgroundRunStore(root)
    alive = store.start(
        [sys.executable, '-c', 'import time; time.sleep(60)'], label='live'
    )
    dead = store.start([sys.executable, '-c', 'import sys; sys.exit(3)'], label='dead')
    store.update_run_id(dead.background_id, 'run-bg-dead-001')
    # Reap the dead child ourselves so the record has a real dead pid.
    os.waitpid(dead.pid, 0)
    return alive.background_id, dead.background_id


def test_cockpit_counts_running_and_orphaned_background_runs(tmp_path: Path) -> None:
    alive_id, dead_id = _seed_running_and_orphaned(tmp_path)
    try:
        cockpit = build_control_cockpit(tmp_path)
    finally:
        BackgroundRunStore(tmp_path).stop(alive_id, timeout_seconds=2.0)

    assert cockpit.background is not None
    assert cockpit.background['running_count'] == 1
    assert cockpit.background['orphaned_count'] == 1
    items = {item['background_id']: item for item in cockpit.background['items']}
    assert set(items) == {alive_id, dead_id}
    assert items[alive_id]['alive'] is True
    assert items[alive_id]['orphaned'] is False
    assert items[dead_id]['alive'] is False
    assert items[dead_id]['orphaned'] is True
    assert items[dead_id]['run_id'] == 'run-bg-dead-001'
    for item in items.values():
        assert set(item) == {
            'background_id',
            'run_id',
            'alive',
            'orphaned',
            'liveness_stale',
            'run_outcome',
        }
    assert 'background runs load failed' not in cockpit.errors


def test_cockpit_panel_renders_background_summary_line(tmp_path: Path) -> None:
    alive_id, _dead_id = _seed_running_and_orphaned(tmp_path)
    try:
        tui = TeaAgentTUI(input_fn=lambda _p: 'exit', output_fn=lambda _: None)
        tui._control_cockpit = build_control_cockpit(tmp_path)
        output = _render_cockpit(tui)
    finally:
        BackgroundRunStore(tmp_path).stop(alive_id, timeout_seconds=2.0)

    assert 'Background: 1 running, 1 orphaned' in output


def test_cockpit_background_is_zero_without_records(tmp_path: Path) -> None:
    cockpit = build_control_cockpit(tmp_path)

    assert cockpit.background == {'running_count': 0, 'orphaned_count': 0, 'items': []}
    assert 'background runs load failed' not in cockpit.errors

    tui = TeaAgentTUI(input_fn=lambda _p: 'exit', output_fn=lambda _: None)
    tui._control_cockpit = cockpit
    assert 'Background: 0 running, 0 orphaned' in _render_cockpit(tui)


def test_cockpit_background_items_are_capped_newest_first(tmp_path: Path) -> None:
    rows = [
        {
            'background_id': f'bg-{i:02d}',
            'run_id': f'run-{i:02d}',
            'alive': i % 2 == 0,
            'orphaned': False,
            'liveness_stale': False,
        }
        for i in range(12)
    ]
    with patch.object(BackgroundRunStore, 'list', return_value=rows):
        cockpit = build_control_cockpit(tmp_path)

    assert cockpit.background is not None
    assert cockpit.background['running_count'] == 6
    assert len(cockpit.background['items']) == 10
    assert [i['background_id'] for i in cockpit.background['items']] == [
        f'bg-{i:02d}' for i in range(10)
    ]


def test_cockpit_background_store_failure_is_recorded_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        patch.object(
            BackgroundRunStore, 'list', side_effect=RuntimeError('bg store boom')
        ),
        caplog.at_level(logging.ERROR, logger='teaagent.cockpit'),
    ):
        cockpit = build_control_cockpit(tmp_path)

    assert cockpit.background is None
    assert 'background runs load failed' in cockpit.errors
    assert any(
        'background' in r.message and r.levelno == logging.ERROR for r in caplog.records
    )

    tui = TeaAgentTUI(input_fn=lambda _p: 'exit', output_fn=lambda _: None)
    tui._control_cockpit = cockpit
    assert 'Background: unknown' in _render_cockpit(tui)


def test_cockpit_background_item_surfaces_run_outcome(tmp_path: Path) -> None:
    """BG-001 §3.2: outcome is a distinct fact from process liveness."""
    store = BackgroundRunStore(tmp_path)
    done = store.start([sys.executable, '-c', 'import sys; sys.exit(0)'], label='done')
    store.update_run_id(done.background_id, 'run-bg-completed-001')
    os.waitpid(done.pid, 0)
    runs_dir = tmp_path / '.teaagent' / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / 'run-bg-completed-001.jsonl').write_text(
        json.dumps(
            {
                'run_id': 'run-bg-completed-001',
                'timestamp': '2026-10-01T00:00:01+00:00',
                'event_type': 'run_completed',
                'payload': {'answer': 'ok'},
            }
        )
        + '\n',
        encoding='utf-8',
    )

    cockpit = build_control_cockpit(tmp_path)

    assert cockpit.background is not None
    items = {item['background_id']: item for item in cockpit.background['items']}
    item = items[done.background_id]
    assert item['alive'] is False
    assert item['run_outcome'] == 'completed'
