"""U-P1-6: TUI typo-confirmation gate tests.

In chat mode, an unknown command (likely a typo) must NOT be silently forwarded
as a task. The TUI must prompt ``unknown command "x"; send as task? [y/N]`` and
default to No.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from teaagent.tui import TeaAgentTUI


def _make_chat_tui(*, input_fn=None, output: list[str] | None = None) -> TeaAgentTUI:
    if output is None:
        output = []
    tui = TeaAgentTUI(input_fn=input_fn, output_fn=output.append)
    tui.chat = True
    controller = MagicMock()
    controller.execute_task.return_value = MagicMock(
        run_result=MagicMock(
            run_id='run-1',
            status='completed',
            iterations=1,
            tool_calls=0,
            cost_cents=0.0,
            input_tokens=1,
            output_tokens=1,
            final_answer=MagicMock(content='ok'),
            metadata={},
            error_message=None,
        ),
        cost_cents=0.0,
    )
    tui._chat_controller = controller
    controller.get_session_cost.return_value = 0.0
    controller.session_state.session_cost_cents = 0.0
    return tui


class _InputRecorder:
    """Records prompts and returns a canned answer."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def test_typo_default_no_does_not_send_as_task() -> None:
    output: list[str] = []
    # Default: empty input / anything other than y → No
    recorder = _InputRecorder('')
    tui = _make_chat_tui(input_fn=recorder, output=output)
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore'),
    ):
        tui.handle_command('asdfqwer')

    # The confirmation prompt must have been shown.
    assert recorder.prompts, 'expected a confirmation prompt to be shown'
    assert 'send as task?' in recorder.prompts[0]
    assert 'asdfqwer' in recorder.prompts[0]
    controller = tui._chat_controller
    controller.execute_task.assert_not_called()


def test_typo_explicit_yes_sends_as_task() -> None:
    output: list[str] = []
    recorder = _InputRecorder('y')
    tui = _make_chat_tui(input_fn=recorder, output=output)
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

        tui.handle_command('fix the bug')

    assert 'send as task?' in recorder.prompts[0]
    controller = tui._chat_controller
    controller.execute_task.assert_called_once()
    assert controller.execute_task.call_args[0][0] == 'fix the bug'


def test_typo_uppercase_yes_sends_as_task() -> None:
    output: list[str] = []
    recorder = _InputRecorder('YES')
    tui = _make_chat_tui(input_fn=recorder, output=output)
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

        tui.handle_command('do something')

    controller = tui._chat_controller
    controller.execute_task.assert_called_once()


def test_typo_random_text_defaults_to_no() -> None:
    output: list[str] = []
    recorder = _InputRecorder('no')
    tui = _make_chat_tui(input_fn=recorder, output=output)
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore'),
    ):
        tui.handle_command('xyzzy')

    controller = tui._chat_controller
    controller.execute_task.assert_not_called()


def test_typo_non_interactive_declines() -> None:
    output: list[str] = []
    # input_fn=None simulates a non-interactive context
    tui = _make_chat_tui(input_fn=None, output=output)
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore'),
    ):
        tui.handle_command('typo-cmd')

    joined = ' '.join(output)
    assert 'send as task?' in joined
    assert 'declined' in joined.lower()
    controller = tui._chat_controller
    controller.execute_task.assert_not_called()


def test_typo_eof_declines() -> None:
    output: list[str] = []

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    tui = _make_chat_tui(input_fn=raise_eof, output=output)
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore'),
    ):
        tui.handle_command('oops')

    controller = tui._chat_controller
    controller.execute_task.assert_not_called()


def test_known_command_not_gated_in_chat_mode() -> None:
    """Real commands must still dispatch without a confirmation prompt."""
    output: list[str] = []
    recorder = _InputRecorder('n')
    tui = _make_chat_tui(input_fn=recorder, output=output)
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore'),
    ):
        tui.handle_command('cost')

    # No confirmation prompt should have been shown for a real command.
    assert not recorder.prompts
