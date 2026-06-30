"""SEC-11: partial undo warning when shell-mutating tools were used."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter
from tui_boundaries import chat_typo_patches

from teaagent.chat_session_controller import ChatSessionController
from teaagent.cli import main
from teaagent.run_undo import PARTIAL_UNDO_SHELL_WARNING, audit_events_used_shell_mutate
from teaagent.tui import TeaAgentTUI


def _shell_event(tool_name: str) -> dict:
    return {
        'event_type': 'tool_call_completed',
        'payload': {'tool_name': tool_name, 'call_id': 'shell-1'},
    }


def _write_event() -> dict:
    return {
        'event_type': 'tool_call_completed',
        'payload': {'tool_name': 'workspace_write_file', 'call_id': 'write-1'},
    }


def test_audit_events_used_shell_mutate_detects_mutate_tools() -> None:
    assert audit_events_used_shell_mutate([_shell_event('workspace_run_shell_mutate')])
    assert audit_events_used_shell_mutate([_shell_event('workspace_run_shell')])
    assert not audit_events_used_shell_mutate(
        [_shell_event('workspace_run_shell_inspect')]
    )
    assert not audit_events_used_shell_mutate([_write_event()])
    assert not audit_events_used_shell_mutate([])


def test_agent_undo_warns_when_run_used_shell_mutate(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"after\\n"},"call_id":"write-1"}',
            '{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"echo shell"},"call_id":"shell-1"}',
            '{"type":"final","content":"done"}',
        ]
    )
    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'run',
                'gpt',
                'write and shell',
                '--root',
                str(tmp_path),
                '--allow-destructive',
                '--skip-plan-check',
                '--max-iterations',
                '6',
                '--max-tool-calls',
                '6',
            ]
        )
    assert run_code == 0

    stderr = io.StringIO()
    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        undo_code = main(['agent', 'undo', '--root', str(tmp_path)])
    assert undo_code == 0
    assert PARTIAL_UNDO_SHELL_WARNING in stderr.getvalue()


def test_agent_undo_silent_for_file_only_run(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"after\\n"},"call_id":"write-1"}',
            '{"type":"final","content":"done"}',
        ]
    )
    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'run',
                'gpt',
                'write only',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'workspace-write',
                '--skip-plan-check',
                '--max-iterations',
                '6',
                '--max-tool-calls',
                '6',
            ]
        )
    assert run_code == 0

    stderr = io.StringIO()
    stdout = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        undo_code = main(['agent', 'undo', '--root', str(tmp_path)])
    assert undo_code == 0
    assert PARTIAL_UNDO_SHELL_WARNING not in stderr.getvalue()


def test_tui_undo_warns_when_run_used_shell_mutate(tmp_path: Path) -> None:
    output: list[str] = []
    tui = TeaAgentTUI(
        root=tmp_path,
        input_fn=lambda _: '',
        output_fn=output.append,
    )
    events = [_write_event(), _shell_event('workspace_run_shell_mutate')]
    with (
        chat_typo_patches(tui),
        patch('teaagent.tui.core.RunStore') as mock_store_cls,
        patch.object(ChatSessionController, 'undo_last_run', return_value=True),
    ):
        mock_store = mock_store_cls.return_value
        mock_store.latest_run_with_undo.return_value = 'run-1'
        mock_store.show_run.return_value = events
        tui._handle_undo()

    joined = '\n'.join(output)
    assert PARTIAL_UNDO_SHELL_WARNING in joined


def test_tui_undo_silent_for_file_only_run(tmp_path: Path) -> None:
    output: list[str] = []
    tui = TeaAgentTUI(
        root=tmp_path,
        input_fn=lambda _: '',
        output_fn=output.append,
    )
    with (
        chat_typo_patches(tui),
        patch('teaagent.tui.core.RunStore') as mock_store_cls,
        patch.object(ChatSessionController, 'undo_last_run', return_value=True),
    ):
        mock_store = mock_store_cls.return_value
        mock_store.latest_run_with_undo.return_value = 'run-1'
        mock_store.show_run.return_value = [_write_event()]
        tui._handle_undo()

    joined = '\n'.join(output)
    assert PARTIAL_UNDO_SHELL_WARNING not in joined
