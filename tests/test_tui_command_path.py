"""P0-A-001 & P0-A-003: Headless command-path tests for TUI semantic parity.

These tests verify that TUI commands (ask, run, /cost, /undo, root, resume)
delegate to ChatSessionController rather than bypassing it with local state.

P0-A-003 tests verify fallback wording: journal undo, checkpoint restore,
or nothing-to-undo messages are explicitly labeled.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


def _make_controller_mock(
    *, undo_last_run: bool = False, session_cost: float = 0.0
) -> MagicMock:
    controller = MagicMock()
    controller.undo_last_run.return_value = undo_last_run
    controller.get_session_cost.return_value = session_cost
    controller.session_state.session_cost_cents = session_cost
    return controller


def _setup_tui_with_controller_mock() -> tuple[TeaAgentTUI, MagicMock, list[str]]:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = _make_controller_mock()
    controller.execute_task.return_value = MagicMock(
        run_result=MagicMock(
            run_id='test-run-123',
            status='completed',
            iterations=1,
            tool_calls=0,
            cost_cents=0.0,
            input_tokens=10,
            output_tokens=5,
            final_answer=MagicMock(content='test output'),
            metadata={},
            error_message=None,
        ),
        cost_cents=0.0,
    )
    tui._chat_controller = controller
    return tui, controller, output


def test_ask_calls_controller_execute_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tui, controller, _output = _setup_tui_with_controller_mock()
        tui.root = Path(tmp)

        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.tui.state.create_llm_adapter'),
            patch('teaagent.tui.core.RunStore') as mock_store_class,
        ):
            mock_store = MagicMock()
            mock_store.show_run.return_value = []
            mock_store.logger_for_result = MagicMock()
            mock_store.audit_logger.return_value = MagicMock()
            mock_store_class.return_value = mock_store

            tui.handle_command('ask test task')

        controller.execute_task.assert_called_once()
        assert controller.execute_task.call_args[0][0] == 'test task'


def test_run_calls_controller_execute_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tui, controller, _output = _setup_tui_with_controller_mock()
        tui.root = Path(tmp)

        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.tui.state.create_llm_adapter'),
            patch('teaagent.tui.core.RunStore') as mock_store_class,
        ):
            mock_store = MagicMock()
            mock_store.show_run.return_value = []
            mock_store.logger_for_result = MagicMock()
            mock_store.audit_logger.return_value = MagicMock()
            mock_store_class.return_value = mock_store

            tui.handle_command('run another task')

        controller.execute_task.assert_called_once()
        assert controller.execute_task.call_args[0][0] == 'another task'


def test_ask_does_not_bypass_controller() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tui, controller, _output = _setup_tui_with_controller_mock()
        tui.root = Path(tmp)

        with (
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.tui.state.create_llm_adapter'),
            patch('teaagent.tui.core.RunStore') as mock_store_class,
        ):
            mock_store = MagicMock()
            mock_store.show_run.return_value = []
            mock_store.logger_for_result = MagicMock()
            mock_store.audit_logger.return_value = MagicMock()
            mock_store_class.return_value = mock_store

            tui.handle_command('ask verify controller path')

        controller.execute_task.assert_called_once()


def test_safe_wrapper_catches_exceptions_and_preserves_controller() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = _make_controller_mock()
    tui._chat_controller = controller

    with patch.object(tui, '_run_agent_task', side_effect=RuntimeError('boom')):
        _safe_run_agent_task(tui, 'test task')

    assert 'error:' in ' '.join(output)
    assert 'boom' in ' '.join(output)


def test_cost_reads_from_controller_get_session_cost() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(session_cost=350.0)
        mock_get.return_value = controller

        tui._handle_cost()

        controller.get_session_cost.assert_called_once()
        assert 'cost: $3.50' in output[-1]


def test_cost_falls_back_to_local_when_controller_is_zero() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(session_cost=0.0)
        mock_get.return_value = controller
        tui._session_cost_cents = 250.0

        tui._handle_cost()

        assert 'cost: $2.50' in output[-1]


def test_cost_command_path_via_handle_command() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(session_cost=123.0)
        mock_get.return_value = controller

        tui.handle_command('cost')

        controller.get_session_cost.assert_called()
        assert 'cost: $1.23' in output[-1]


def test_cost_slash_alias_uses_same_controller_path() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(session_cost=42.0)
        mock_get.return_value = controller

        tui.handle_command('/cost')

        controller.get_session_cost.assert_called()
        assert 'cost: $0.42' in output[-1]


def test_undo_calls_controller_undo_last_run() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(undo_last_run=True)
        mock_get.return_value = controller

        tui._handle_undo()

        controller.undo_last_run.assert_called_once()


def test_undo_journal_wording() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with patch.object(tui, '_get_chat_controller') as mock_get:
        controller = _make_controller_mock(undo_last_run=True)
        mock_get.return_value = controller

        tui._handle_undo()

        assert 'journal undo completed' in output[-1]


# NOTE: test_undo_checkpoint_wording removed — U-P2-3 made TUI undo journal-only
# (no checkpoint fallback). See tests/tui/test_tui_undo_scope.py.


def test_undo_nothing_wording() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)

    with (
        patch.object(tui, '_get_chat_controller') as mock_get,
        patch.object(tui, '_restore_checkpoint', return_value=False),
    ):
        controller = _make_controller_mock(undo_last_run=False)
        mock_get.return_value = controller

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
        patch.object(tui, '_restore_checkpoint', return_value=False),
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
        controller = _make_controller_mock()
        controller.execute_task.return_value = MagicMock(
            run_result=MagicMock(
                run_id='test-resume-456',
                status='completed',
                iterations=1,
                tool_calls=0,
                cost_cents=0.0,
                input_tokens=5,
                output_tokens=3,
                final_answer=MagicMock(content='resumed output'),
                metadata={},
                error_message=None,
            ),
            cost_cents=0.0,
        )
        tui._chat_controller = controller

        from teaagent.run_store import RunStore

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
            patch.object(tui, '_start_file_watcher'),
            patch.object(tui, '_load_tui_state'),
            patch.object(tui, '_save_tui_state'),
            patch('teaagent.tui.state.create_llm_adapter'),
            patch('teaagent.tui.core.RunStore') as mock_store_class,
        ):
            mock_store = MagicMock()
            mock_store.show_run.return_value = []
            mock_store.logger_for_result = MagicMock()
            mock_store.audit_logger.return_value = MagicMock()
            mock_store_class.return_value = mock_store

            tui.handle_command(f'resume {run_id}')

        controller.execute_task.assert_called_once()
        assert controller.execute_task.call_args[0][0] == 'resumed task content'


def test_resume_requires_run_id() -> None:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = _make_controller_mock()
    tui._chat_controller = controller

    tui.handle_command('resume')

    assert 'requires a run id' in output[-1]
    controller.execute_task.assert_not_called()


def test_resume_unknown_run_id() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output: list[str] = []
        tui = TeaAgentTUI(root=tmp, input_fn=lambda _: '', output_fn=output.append)
        controller = _make_controller_mock()
        tui._chat_controller = controller

        tui.handle_command('resume no-such-run-id')

        assert 'error:' in output[-1]
        controller.execute_task.assert_not_called()


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
