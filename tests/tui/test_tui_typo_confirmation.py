"""U-P1-6: TUI typo-confirmation gate tests.

In chat mode, an unknown command (likely a typo) must NOT be silently forwarded
as a task. The TUI must prompt ``unknown command "x"; send as task? [y/N]`` and
default to No.
"""

from __future__ import annotations

import tempfile
from unittest.mock import patch

from tui_boundaries import chat_typo_patches, completed_run_result

from teaagent.chat_session_controller import ChatSessionController
from teaagent.tui import TeaAgentTUI


def _make_chat_tui(
    *,
    input_fn=None,
    output: list[str] | None = None,
    root: str | None = None,
) -> TeaAgentTUI:
    if output is None:
        output = []
    kwargs: dict[str, object] = {
        'input_fn': input_fn,
        'output_fn': output.append,
    }
    if root is not None:
        kwargs['root'] = root
    tui = TeaAgentTUI(**kwargs)
    tui.chat = True
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
    recorder = _InputRecorder('')
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=recorder, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('asdfqwer')

        assert recorder.prompts, 'expected a confirmation prompt to be shown'
        assert 'send as task?' in recorder.prompts[0]
        assert 'asdfqwer' in recorder.prompts[0]
        spy_execute.assert_not_called()


def test_typo_explicit_yes_sends_as_task() -> None:
    output: list[str] = []
    recorder = _InputRecorder('y')
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=recorder, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(
                tui,
                run_result=completed_run_result(run_id='typo-run-1'),
                execute_task=True,
            ),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('fix the bug')

        assert 'send as task?' in recorder.prompts[0]
        spy_execute.assert_called_once()
        assert spy_execute.call_args[0][0] == 'fix the bug'


def test_typo_uppercase_yes_sends_as_task() -> None:
    output: list[str] = []
    recorder = _InputRecorder('YES')
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=recorder, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(
                tui,
                run_result=completed_run_result(run_id='typo-run-2'),
                execute_task=True,
            ),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('do something')

        spy_execute.assert_called_once()


def test_typo_random_text_defaults_to_no() -> None:
    output: list[str] = []
    recorder = _InputRecorder('no')
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=recorder, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('xyzzy')

        spy_execute.assert_not_called()


def test_typo_non_interactive_declines() -> None:
    output: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=None, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('typo-cmd')

        joined = ' '.join(output)
        assert 'send as task?' in joined
        assert 'declined' in joined.lower()
        spy_execute.assert_not_called()


def test_typo_eof_declines() -> None:
    output: list[str] = []

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=raise_eof, output=output, root=tmp)
        controller = tui._get_chat_controller()
        with (
            chat_typo_patches(tui),
            patch.object(
                ChatSessionController,
                'execute_task',
                wraps=controller.execute_task,
            ) as spy_execute,
        ):
            tui.handle_command('oops')

        spy_execute.assert_not_called()


def test_known_command_not_gated_in_chat_mode() -> None:
    """Real commands must still dispatch without a confirmation prompt."""
    output: list[str] = []
    recorder = _InputRecorder('n')
    with tempfile.TemporaryDirectory() as tmp:
        tui = _make_chat_tui(input_fn=recorder, output=output, root=tmp)
        with chat_typo_patches(tui):
            tui.handle_command('cost')

        assert not recorder.prompts
