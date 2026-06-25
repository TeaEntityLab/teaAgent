"""Acceptance tests for prompt_toolkit TUI integration."""

from __future__ import annotations

import builtins
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import PropertyMock, patch

import pytest

from teaagent.tui import TeaAgentTUI


@pytest.mark.skipif(
    importlib.util.find_spec('prompt_toolkit') is None,
    reason='prompt_toolkit is not installed',
)
def test_tui_uses_prompt_toolkit_session() -> None:
    """
    Verify that TeaAgentTUI uses prompt_toolkit.PromptSession for interaction.
    """
    # We need to mock prompt_toolkit.PromptSession
    with patch('prompt_toolkit.PromptSession') as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.prompt.side_effect = ['help', 'exit']

        with TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / '.teaagent' / 'tui_state.json'
            with patch.object(
                TeaAgentTUI, '_state_path', new_callable=PropertyMock
            ) as mock_state_path:
                mock_state_path.return_value = state_path
                tui = TeaAgentTUI(root=root, input_fn=None)

                output_lines: list[str] = []
                tui.output_fn = output_lines.append

                tui.run()

            # Verify PromptSession was created
            assert mock_session_cls.called
            assert state_path.parent.exists()

            # Verify history is persistent (it should be linked to a file)
            args, kwargs = mock_session_cls.call_args
            assert 'history' in kwargs
            from prompt_toolkit.history import FileHistory

            assert isinstance(kwargs['history'], FileHistory)

            # Verify prompt was called
            assert mock_session.prompt.called


def test_tui_falls_back_without_prompt_toolkit() -> None:
    original_import = builtins.__import__

    def _mock_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name.startswith('prompt_toolkit'):
            raise ImportError('prompt_toolkit unavailable')
        return original_import(name, globals, locals, fromlist, level)

    with (
        patch('builtins.__import__', side_effect=_mock_import),
        TemporaryDirectory() as td,
    ):
        root = Path(td)
        state_path = root / '.teaagent' / 'tui_state.json'
        with patch.object(
            TeaAgentTUI, '_state_path', new_callable=PropertyMock
        ) as mock_state_path:
            mock_state_path.return_value = state_path
            with patch('builtins.input', side_effect=['help', 'exit']) as mock_input:
                tui = TeaAgentTUI(root=root, input_fn=None)
                output_lines: list[str] = []
                tui.output_fn = output_lines.append
                tui.run()
                assert mock_input.called
