"""Acceptance tests for prompt_toolkit TUI integration."""

from __future__ import annotations

import builtins
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, PropertyMock, patch

from teaagent.tui import TeaAgentTUI


class TestTUIInteractive(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec('prompt_toolkit') is not None,
        'prompt_toolkit is not installed',
    )
    def test_tui_uses_prompt_toolkit_session(self) -> None:
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

                    # Mock output to avoid printing to console
                    tui.output_fn = MagicMock()

                    tui.run()

                # Verify PromptSession was created
                self.assertTrue(mock_session_cls.called)

                # Verify history is persistent (it should be linked to a file)
                args, kwargs = mock_session_cls.call_args
                self.assertIn('history', kwargs)
                from prompt_toolkit.history import FileHistory

                self.assertIsInstance(kwargs['history'], FileHistory)

                # Verify prompt was called
                self.assertTrue(mock_session.prompt.called)

    def test_tui_falls_back_without_prompt_toolkit(self) -> None:
        original_import = builtins.__import__

        def _mock_import(
            name: str, globals=None, locals=None, fromlist=(), level: int = 0
        ):
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
                with patch(
                    'builtins.input', side_effect=['help', 'exit']
                ) as mock_input:
                    tui = TeaAgentTUI(root=root, input_fn=None)
                    tui.output_fn = MagicMock()
                    tui.run()
                    self.assertTrue(mock_input.called)
