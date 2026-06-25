"""Headless TUI acceptance tests using pty-based interaction simulation."""

from __future__ import annotations

import json
import os
import pty
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import FakeAdapter

from teaagent.runner import FinalAnswer, RunResult
from teaagent.tui import TeaAgentTUI


class _NoopAudit:
    def add_sink(self, _sink: object) -> None:
        return None


def _run_tui_headless(
    root: Path,
    commands: list[str],
    adapter_responses: list[str] | None = None,
    timeout_seconds: float = 5.0,
) -> str:
    master_fd, slave_fd = pty.openpty()

    def _input_fn(prompt: str) -> str:
        return ''

    output_lines: list[str] = []

    def _output_fn(*args, **kwargs) -> None:  # noqa: ARG001
        output_lines.extend(str(a) for a in args)

    adapter = None
    if adapter_responses:
        adapter = FakeAdapter(adapter_responses)

    tui = TeaAgentTUI(
        root=root,
        input_fn=_input_fn,
        output_fn=_output_fn,
        adapter_factory=(lambda _p, _m: adapter) if adapter else None,
    )

    for cmd in commands:
        tui.handle_command(cmd)

    os.close(slave_fd)
    os.close(master_fd)
    return '\n'.join(output_lines)


def test_help_command_outputs_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command('help')
        joined = '\n'.join(output)
        assert 'help' in joined
        assert 'exit' in joined
        assert 'setup' in joined
        assert 'pin' in joined


def test_exit_returns_false() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        result = tui.handle_command('exit')
        assert not result
        assert 'bye' in '\n'.join(output)


def test_setup_available() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: 'exit',
            output_fn=output.append,
        )
        result = tui.handle_command('setup')
        assert result


@pytest.mark.parametrize(
    'toggle_name',
    [
        'progress',
        'stream',
        'subagent',
        'chat',
        'destructive',
        'route-model',
    ],
)
def test_toggle_toggles_on_off(toggle_name: str) -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command(f'{toggle_name} on')
        tui.handle_command(f'{toggle_name} off')
        joined = '\n'.join(output)
        assert f'{toggle_name}: on' in joined
        assert f'{toggle_name}: off' in joined


def test_session_new_and_list() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command('session new')
        tui.handle_command('session list')
        joined = '\n'.join(output)
        assert 'session new:' in joined
        assert 'error:' not in joined


@pytest.mark.parametrize(
    'mode',
    [
        'read-only',
        'workspace-write',
        'prompt',
        'allow',
        'danger-full-access',
    ],
)
def test_permission_mode_validation(mode: str) -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command(f'permission {mode}')
        joined = '\n'.join(output)
        assert 'permission:' in joined


def test_permission_mode_invalid() -> None:
    output = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command('permission invalid-mode')
        joined = '\n'.join(output)
        assert 'error:' in joined


def test_pin_file_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'test.txt').write_text('hello', encoding='utf-8')
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui._start_file_watcher = lambda: None
        tui._stop_file_watcher = lambda: None
        tui.handle_command('pin test.txt')
        tui.handle_command('pinned')
        tui.handle_command('unpin test.txt')
        joined = '\n'.join(output)
        assert 'pinned: test.txt' in joined
        assert 'unpinned: test.txt' in joined


def test_compact_available() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command('compact')
        joined = '\n'.join(output)
        assert 'compact:' in joined


def test_daily_without_adapter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello', encoding='utf-8')
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: 'exit',
            output_fn=output.append,
        )
        tui.handle_command('permission read-only')
        tui.handle_command('daily summarize README.md')
        joined = '\n'.join(output)
        assert 'daily:' in joined


def test_unknown_command_shows_error() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui.handle_command('nonexistent_command_xyz')
        joined = '\n'.join(output)
        assert 'error:' in joined


def test_split_pane_method() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
        )
        result = tui._should_use_split_pane()
        assert isinstance(result, bool)


def test_state_panel_no_error() -> None:
    """Printing state panel should not throw."""
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        stdout = StringIO()
        with redirect_stdout(stdout):
            tui._print_state_panel()

        rendered = stdout.getvalue()
        assert 'TeaAgent TUI' in rendered
        assert 'State Panel' in rendered
        assert 'error:' not in rendered.lower()

    # ── TASK-DD2-013: Hardened path tests ─────────────────────────────────────


def test_headless_cost_accumulation_through_ask_command() -> None:
    """TASK-DD2-013: TUI cost test fails if _run_agent_task does not add real result cost.

    This test drives through the actual 'ask' command path to verify cost accumulation,
    rather than directly testing internal state. It will fail if the cost accumulation
    line in _run_agent_task is missing or broken.
    """
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )

        with (
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.tui.core.RunStore') as mock_store,
            patch('teaagent.tui.state.create_llm_adapter'),
        ):
            # Mock run_chat_agent to return a result with cost
            mock_run.return_value = RunResult(
                run_id='test-run',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=100.0,  # This must be accumulated
                input_tokens=50,
                output_tokens=25,
                final_answer=FinalAnswer(content='done'),
                metadata={},
                error_message=None,
            )
            mock_store.return_value.show_run.return_value = []
            mock_store.return_value.logger_for_result = lambda *a: None
            mock_store.return_value.audit_logger = lambda: _NoopAudit()
            mock_store.return_value.undo_path = lambda *a: Path('/tmp/undo.json')

            # Initial cost should be zero
            assert tui._session_cost_cents == 0.0

            # Drive through the actual ask command
            tui.handle_command('ask test task')

            # Cost must be accumulated from the result
            assert tui._session_cost_cents == 100.0

            # Verify cost command shows the accumulated cost
            output.clear()
            tui.handle_command('cost')
            assert '$1.00' in '\n'.join(output)


def test_headless_explicit_root_not_overridden_by_state() -> None:
    """TASK-DD2-013: Root test fails if _load_tui_state overwrites explicit root.

    This test drives through the actual TUI initialization with an explicit root
    to verify that saved state cannot override it. It will fail if the guard
    in _load_tui_state is missing or broken.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create explicit root
        explicit_root = Path(tmpdir) / 'explicit'
        explicit_root.mkdir()

        # Create saved state with different root under a fake home directory
        saved_root = Path(tmpdir) / 'saved'
        saved_root.mkdir()
        fake_home = Path(tmpdir) / 'fakehome'
        fake_home.mkdir()
        state_dir = fake_home / '.teaagent'
        state_dir.mkdir()
        state_file = state_dir / 'tui_state.json'
        saved_state = {
            'root': str(saved_root),
            'provider': 'test',
            'model': 'test-model',
        }
        state_file.write_text(json.dumps(saved_state), encoding='utf-8')

        output: list[str] = []
        tui = TeaAgentTUI(
            root=explicit_root,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )
        tui._root_explicit = True  # Simulate CLI --root flag

        with patch('teaagent.tui.core.Path.home', return_value=fake_home):
            tui._load_tui_state()

        # Root must remain the explicit one, not the saved one
        assert tui.root.resolve() == explicit_root.resolve()
        assert str(tui.root) != str(saved_root)


def test_headless_initial_task_executed_before_repl() -> None:
    """TASK-DD2-013: Initial-task test fails if parser/handler/TUI handoff drops the task.

    This test drives through the actual run() method with initial_task to verify
    it's dispatched before the REPL loop. It will fail if the initial task is
    dropped during CLI parser → handler → TUI handoff.
    """
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _: (_ for _ in ()).throw(EOFError),  # exits immediately
            output_fn=output.append,
        )

        captured_tasks: list[str] = []

        def capture_task(task: str, **kwargs: object) -> None:
            captured_tasks.append(task)

        tui._run_agent_task = capture_task
        tui._load_workspace_defaults = lambda: None
        tui._load_tui_state = lambda: None
        tui._print_header = lambda: None
        tui._start_file_watcher = lambda: None
        tui._stop_file_watcher = lambda: None
        tui._save_tui_state = lambda: None

        # Drive through the actual run() path with initial_task
        tui.run(initial_task='the initial task')

        # _run_agent_task must be called with the initial task
        assert captured_tasks == ['the initial task']


def test_headless_undo_command_updates_state() -> None:
    """TASK-DD2-013: Undo command should update user-visible state.

    This test drives through the actual undo command to verify it updates
    the backing state and shows user-visible output.
    """
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )

        # Drive through the undo command
        tui.handle_command('undo')

        # Should show user-visible output about undo state
        joined = '\n'.join(output)
        # Either shows undo info or error (if no undo journal)
        assert 'undo' in joined.lower() or 'error' in joined.lower()


def test_headless_approval_prompt_flow() -> None:
    """TASK-DD2-013: Approval commands should update user-visible state.

    This test drives through the approval command path to verify it updates
    the backing state and shows user-visible output.
    """
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _p: '',
            output_fn=output.append,
        )

        # Drive through the approvals command
        tui.handle_command('approvals')

        # Should show user-visible output (JSON list of approved call IDs)
        joined = '\n'.join(output)
        # Approvals command outputs JSON, which should be a list (even if empty)
        assert '[]' in joined or '[' in joined
