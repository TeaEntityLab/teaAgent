"""P0-A-001 & P0-A-003: Headless command-path tests for TUI semantic parity.

These tests verify that TUI commands (ask, run, /cost, /undo, root, resume)
delegate to ChatSessionController rather than bypassing it with local state.

P0-A-003 tests verify fallback wording: journal undo, checkpoint restore,
or nothing-to-undo messages are explicitly labeled.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

from teaagent.chat_session_controller import ChatSessionController
from teaagent.run_store import RunStore
from teaagent.tui import TeaAgentTUI
from teaagent.tui._commands import _safe_run_agent_task
from teaagent.types import FinalAnswer, RunResult


def _completed_run_result(
    *,
    run_id: str = 'cost-test-run',
    cost_cents: float = 0.0,
    content: str = 'done',
) -> RunResult:
    return RunResult(
        run_id=run_id,
        status='completed',
        iterations=1,
        tool_calls=0,
        cost_cents=cost_cents,
        input_tokens=100,
        output_tokens=50,
        final_answer=FinalAnswer(content=content),
        metadata={},
        error_message=None,
    )


@contextmanager
def _command_path_boundary(
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[None]:
    """CG-16 boundary: real controller/store, mock LLM + show_run only."""
    result = run_result or _completed_run_result()
    patches = [
        patch(
            'teaagent.chat_session_controller.run_chat_agent',
            return_value=result,
        ),
        patch('teaagent.tui.state.create_llm_adapter'),
    ]
    if patch_show_run:
        patches.append(patch('teaagent.tui.core.RunStore.show_run', return_value=[]))
    from contextlib import ExitStack

    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        yield


@contextmanager
def _ask_run_patches(
    tui: TeaAgentTUI,
    *,
    run_result: RunResult | None = None,
    patch_show_run: bool = True,
) -> Iterator[None]:
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        _command_path_boundary(run_result=run_result, patch_show_run=patch_show_run),
    ):
        yield


def test_ask_calls_controller_execute_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        with (
            _ask_run_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=ChatSessionController.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('ask test task')

        spy_execute.assert_called_once()
        assert spy_execute.call_args[0][0] == 'test task'


def test_run_calls_controller_execute_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        with (
            _ask_run_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=ChatSessionController.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('run another task')

        spy_execute.assert_called_once()
        assert spy_execute.call_args[0][0] == 'another task'


def test_ask_does_not_bypass_controller() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        with (
            _ask_run_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=ChatSessionController.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('ask verify controller path')

        spy_execute.assert_called_once()


def test_safe_wrapper_catches_exceptions_and_preserves_controller() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_run_agent_task', side_effect=RuntimeError('boom')):
        _safe_run_agent_task(tui, 'test task')

    assert 'error:' in ' '.join(output)
    assert 'boom' in ' '.join(output)


def test_cost_reads_from_controller_get_session_cost() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 350.0

    with patch.object(
        controller, 'get_session_cost', wraps=controller.get_session_cost
    ) as spy_cost:
        tui._handle_cost()
        spy_cost.assert_called_once()

    assert 'cost: $3.50' in output[-1]


def test_cost_falls_back_to_local_when_controller_is_zero() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 0.0
    tui._session_cost_cents = 250.0

    tui._handle_cost()

    assert 'cost: $2.50' in output[-1]


def test_cost_command_path_via_handle_command() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 123.0

    with patch.object(
        controller, 'get_session_cost', wraps=controller.get_session_cost
    ) as spy_cost:
        tui.handle_command('cost')
        spy_cost.assert_called()

    assert 'cost: $1.23' in output[-1]


def test_cost_slash_alias_uses_same_controller_path() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 42.0

    with patch.object(
        controller, 'get_session_cost', wraps=controller.get_session_cost
    ) as spy_cost:
        tui.handle_command('/cost')
        spy_cost.assert_called()

    assert 'cost: $0.42' in output[-1]


def test_undo_calls_controller_undo_last_run() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()

    with patch.object(
        controller, 'undo_last_run', wraps=controller.undo_last_run
    ) as spy_undo:
        tui._handle_undo()
        spy_undo.assert_called_once()


def test_undo_journal_wording() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = tui._get_chat_controller()

    def _journal_undo() -> bool:
        return True

    controller.undo_last_run = _journal_undo
    tui._handle_undo()

    assert 'journal undo completed' in output[-1]


# NOTE: test_undo_checkpoint_wording removed — U-P2-3 made TUI undo journal-only
# (no checkpoint fallback). See tests/tui/test_tui_undo_scope.py.


def test_undo_nothing_wording() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    tui._handle_undo()

    assert 'nothing to undo' in output[-1]


# NOTE: test_undo_checkpoint_wording_mentions_stale_journal removed — U-P2-3
# made TUI undo journal-only. See tests/tui/test_tui_undo_scope.py.


def test_undo_without_controller_is_handled() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with (
        patch.object(
            tui,
            '_get_chat_controller',
            side_effect=RuntimeError('no controller'),
        ),
        pytest.raises(RuntimeError),
    ):
        tui._handle_undo()


def test_root_before_controller_creation() -> None:
    with (
        tempfile.TemporaryDirectory() as tmp1,
        tempfile.TemporaryDirectory() as tmp2,
    ):
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp1, input_fn=lambda _: '', output_fn=output.append)

        tui.handle_command(f'root {tmp2}')

        assert tui.root == Path(tmp2).resolve()
        controller = tui._get_chat_controller()
        assert controller.root == Path(tmp2).resolve()


def test_root_after_controller_creation() -> None:
    with (
        tempfile.TemporaryDirectory() as tmp1,
        tempfile.TemporaryDirectory() as tmp2,
    ):
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp1, input_fn=lambda _: '', output_fn=output.append)

        controller1 = tui._get_chat_controller()
        assert controller1.root == Path(tmp1).resolve()

        tui.handle_command(f'root {tmp2}')
        assert tui.root == Path(tmp2).resolve()
        assert controller1.root == Path(tmp1).resolve()


def test_root_command_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

        tui.handle_command(f'root {tmp}')

        assert f'root: {Path(tmp).resolve()}' in output


def test_resume_goes_through_controller_execute_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        store = RunStore(tmp)
        run_id = 'resume-test-789'
        run_path = store.run_path(run_id)
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    'run_id': run_id,
                    'created_at': '2026-06-05T00:00:00Z',
                    'event_type': 'run_started',
                    'payload': {'task': 'resumed task content'},
                }
            )
            + '\n',
            encoding='utf-8',
        )

        with (
            _ask_run_patches(
                tui,
                run_result=_completed_run_result(run_id=run_id),
                patch_show_run=False,
            ),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=ChatSessionController.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command(f'resume {run_id}')

        spy_execute.assert_called_once()
        assert spy_execute.call_args[0][0] == 'resumed task content'


def test_resume_requires_run_id() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(
        ChatSessionController,
        'execute_task',
        wraps=ChatSessionController.execute_task,
    ) as spy_execute:
        tui.handle_command('resume')

    assert 'requires a run id' in output[-1]
    spy_execute.assert_not_called()


def test_resume_unknown_run_id() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)

        with patch.object(
            ChatSessionController,
            'execute_task',
            wraps=ChatSessionController.execute_task,
        ) as spy_execute:
            tui.handle_command('resume no-such-run-id')

        assert 'error:' in output[-1]
        spy_execute.assert_not_called()


def test_session_cost_cents_property_delegates_to_controller() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 500.0

    assert tui._session_cost_cents == 500.0


def test_session_cost_cents_setter_delegates_to_controller() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    tui._session_cost_cents = 750.0

    controller = tui._get_chat_controller()
    assert controller.session_state.session_cost_cents == 750.0


def test_get_session_cost_cents_uses_controller() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 333.0

    result = tui._get_session_cost_cents()
    assert result == 333.0


def test_run_agent_task_accumulates_cost_in_controller() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)

        controller = tui._get_chat_controller()
        assert controller.session_state.session_cost_cents == 0.0

        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch(
                'teaagent.chat_session_controller.run_chat_agent',
                return_value=_completed_run_result(cost_cents=175.0),
            ),
            patch('teaagent.tui.core.RunStore.show_run', return_value=[]),
            patch('teaagent.tui.state.create_llm_adapter'),
        ):
            tui._run_agent_task('cost accum task')

        assert tui._session_cost_cents == 175.0
        assert controller.session_state.session_cost_cents == 175.0
