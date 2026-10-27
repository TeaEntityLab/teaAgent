# test-type: contract
"""Operator cockpit contract tests (docs/specs/operator-cockpit-contract-2026-06-01.md).

Acceptance section of the contract names four tests. They are implemented
here against the real cockpit code:

- test_cockpit_state_single_source: CLI snapshot and TUI panel render from
  one build_control_cockpit() instance (single computation).
- test_cockpit_shows_blocked: a paused run with a pending approval is
  reported by the cockpit and rendered by the TUI panel.
- test_cockpit_no_clear_screen: the TUI cockpit render emits no clear-screen
  sequence.
- test_cockpit_recoverable_matches_undo_journal: undo availability agrees
  with the latest run's undo journal.

Contract rule 4 (exact undo_command, already produced by summarize_run) is
covered by the undo_command tests at the end of this file.

The contract's Dashboard surface has no implementation in this codebase, so
the single-source test covers the CLI snapshot and the TUI panel only.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.cockpit import ControlCockpitState, build_control_cockpit
from teaagent.ergonomics.run_summary import summarize_run
from teaagent.integration import cockpit_parity
from teaagent.integration.cockpit_parity import build_cockpit_snapshot
from teaagent.run_store import RunStore
from teaagent.run_undo import UndoJournal
from teaagent.tui import TeaAgentTUI
from teaagent.types import AuditLogger

CLEAR_SCREEN_SEQUENCES = ('\x1b[2J', '\x1b[3J', '\x1bc', '\x1b[H\x1b[2J', '\033[2J')


def _seed_run_with_undo(root: Path, run_id: str) -> None:
    """Run a real agent write so the run record and undo journal both exist."""
    store = RunStore(root)
    audit = AuditLogger(path=store.run_path(run_id))
    journal = UndoJournal(root)
    audit.add_sink(journal)
    adapter = FakeAdapter(
        [
            (
                '{"type":"tool","tool_name":"workspace_write_file",'
                '"arguments":{"path":"notes.txt","content":"new\\n"},"call_id":"w1"}'
            ),
            '{"type":"final","content":"done"}',
        ]
    )
    run_chat_agent(
        ChatAgentConfig.from_root(
            root, allow_destructive=True, max_iterations=4, max_tool_calls=4
        ),
        'write notes',
        adapter=adapter,
        audit=audit,
        run_id=run_id,
    )
    journal.save_to(store.undo_path(run_id))


def _write_paused_run(root: Path, run_id: str, call_id: str) -> None:
    """Write a run that is paused on one unresolved pending approval."""
    now = datetime.now(timezone.utc).isoformat()
    events: list[dict[str, Any]] = [
        {
            'event_type': 'run_started',
            'run_id': run_id,
            'created_at': now,
            'payload': {'task': 'write docs'},
        },
        {
            'event_type': 'tool_call_pending_approval',
            'run_id': run_id,
            'created_at': now,
            'payload': {
                'call_id': call_id,
                'tool_name': 'workspace_write_file',
                'arguments': {'path': 'docs/cli.md', 'content': 'x'},
                'reason': 'destructive tool requires approval',
                'reason_code': 'destructive',
                'annotations': {'destructive': True},
            },
        },
    ]
    path = RunStore(root).run_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n'.join(json.dumps(e, sort_keys=True) for e in events) + '\n',
        encoding='utf-8',
    )


def _tui() -> TeaAgentTUI:
    return TeaAgentTUI(input_fn=lambda _p: 'exit', output_fn=lambda _: None)


def _render_panel(tui: TeaAgentTUI) -> str:
    buffer = StringIO()
    with (
        patch('sys.stdout', buffer),
        patch('shutil.get_terminal_size', return_value=(120, 30)),
    ):
        tui._print_state_panel()
    return buffer.getvalue()


def test_cockpit_state_single_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI snapshot and TUI panel render from the same ControlCockpitState."""
    _seed_run_with_undo(tmp_path, 'run-single-001')

    built: list[ControlCockpitState] = []
    real_build = build_control_cockpit

    def spy(*args: Any, **kwargs: Any) -> ControlCockpitState:
        state = real_build(*args, **kwargs)
        built.append(state)
        return state

    monkeypatch.setattr(cockpit_parity, 'build_control_cockpit', spy)

    snapshot = build_cockpit_snapshot(tmp_path, permission_mode='prompt')

    # Single computation: exactly one state is produced for the CLI surface.
    assert len(built) == 1
    state = built[0]

    # CLI surface projects the same instance field-for-field.
    assert snapshot['control'] == asdict(state)

    # TUI surface renders the same instance: every matrix field it shows
    # matches the shared state.
    tui = _tui()
    tui._control_cockpit = state
    output = _render_panel(tui)
    assert f'Branch: {state.branch}' in output
    assert f'Undo: {state.undo}' in output
    assert f'Last run: {state.last_run_id}' in output
    assert f'Approval: {state.approval["pending_count"]} pending' in output
    assert f'Memory: {state.memory["total_entries"]} entries' in output


def test_cockpit_shows_blocked(tmp_path: Path) -> None:
    """A paused run with a pending approval is reported as blocked/pending.

    Contract: "a run with a pending approval appears in blocked on all three
    surfaces". The cockpit's blocked signal is the approval queue
    (approval.pending_count, plus the snapshot's pending_approvals.pending).
    """
    _write_paused_run(tmp_path, 'run-blocked-001', call_id='call-blocked-1')

    snapshot = build_cockpit_snapshot(tmp_path)
    queue = snapshot['pending_approvals']
    assert queue['queue_depth'] == 1
    assert [p['run_id'] for p in queue['pending']] == ['run-blocked-001']
    assert snapshot['control']['approval']['pending_count'] == 1

    tui = _tui()
    tui._control_cockpit = build_control_cockpit(tmp_path)
    output = _render_panel(tui)
    assert 'Approval: 1 pending' in output


def test_cockpit_no_clear_screen(tmp_path: Path) -> None:
    """The TUI cockpit render emits no clear-screen sequence."""
    _seed_run_with_undo(tmp_path, 'run-clear-001')
    _write_paused_run(tmp_path, 'run-clear-002', call_id='call-clear-1')

    tui = _tui()
    tui._control_cockpit = build_control_cockpit(tmp_path)
    output = _render_panel(tui)

    assert '[Control Cockpit]' in output
    for sequence in CLEAR_SCREEN_SEQUENCES:
        assert sequence not in output


def test_cockpit_recoverable_matches_undo_journal(tmp_path: Path) -> None:
    """Undo availability agrees with the latest run's undo journal entries."""
    store = RunStore(tmp_path)

    # No journal anywhere: undo must be none.
    empty = build_control_cockpit(tmp_path)
    assert empty.undo == 'none'

    _seed_run_with_undo(tmp_path, 'run-recover-001')
    cockpit = build_control_cockpit(tmp_path)

    journal_path = store.undo_path('run-recover-001')
    assert journal_path.is_file()
    journal = UndoJournal(tmp_path, path=journal_path)
    assert journal.has_entries
    assert cockpit.last_run_id == 'run-recover-001'
    assert cockpit.undo == 'available'

    # The journal's changed paths are the same files the run summary reports.
    events = store.show_run('run-recover-001')
    summary = summarize_run(
        root=tmp_path,
        run_id='run-recover-001',
        events=events,
        cost_cents=0.0,
        input_tokens=0,
        output_tokens=0,
    )
    assert summary['files_changed'] == journal.changed_paths()
    assert summary['files_changed_count'] >= 1


def test_cockpit_undo_command_is_exact_and_gated(tmp_path: Path) -> None:
    """undo_command is the summarize_run command, present only when undo is possible."""
    none_state = build_control_cockpit(tmp_path)
    assert none_state.undo == 'none'
    assert none_state.undo_command is None

    _seed_run_with_undo(tmp_path, 'run-cmd-001')
    cockpit = build_control_cockpit(tmp_path)

    summary = summarize_run(
        root=tmp_path,
        run_id='run-cmd-001',
        events=RunStore(tmp_path).show_run('run-cmd-001'),
        cost_cents=0.0,
        input_tokens=0,
        output_tokens=0,
    )
    assert cockpit.undo == 'available'
    assert (
        cockpit.undo_command == summary['undo_command'] == 'teaagent undo run-cmd-001'
    )


def test_cockpit_undo_command_renders_on_undo_line(tmp_path: Path) -> None:
    """The TUI Undo line shows the exact undo command."""
    _seed_run_with_undo(tmp_path, 'run-cmd-002')
    tui = _tui()
    tui._control_cockpit = build_control_cockpit(tmp_path)
    output = _render_panel(tui)

    undo_lines = [line for line in output.splitlines() if 'Undo:' in line]
    assert len(undo_lines) == 1
    assert 'Undo: available' in undo_lines[0]
    assert 'teaagent undo run-cmd-002' in undo_lines[0]
