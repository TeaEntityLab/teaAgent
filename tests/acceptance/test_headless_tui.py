"""Headless TUI acceptance tests using pty-based interaction simulation."""
from __future__ import annotations

import os
import pty
import tempfile
import unittest
from pathlib import Path

from conftest import FakeAdapter

from teaagent.tui import TeaAgentTUI


class HeadlessTUITests(unittest.TestCase):
    """Test TUI behavior with pty-based headless stdin/stdout simulation."""

    def _run_tui_headless(
        self,
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

    def test_help_command_outputs_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui.handle_command('help')
            joined = '\n'.join(output)
            self.assertIn('help', joined)
            self.assertIn('exit', joined)
            self.assertIn('setup', joined)
            self.assertIn('pin', joined)

    def test_exit_returns_false(self) -> None:
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            result = tui.handle_command('exit')
            self.assertFalse(result)
            self.assertIn('bye', '\n'.join(output))

    def test_setup_available(self) -> None:
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: 'exit',
                output_fn=output.append,
            )
            result = tui.handle_command('setup')
            self.assertTrue(result)

    def test_toggle_toggles_on_off(self) -> None:
        toggles = [
            'progress',
            'stream',
            'subagent',
            'chat',
            'destructive',
            'route-model',
        ]
        for toggle_name in toggles:
            with self.subTest(toggle=toggle_name):
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
                    self.assertIn(f'{toggle_name}: on', joined)
                    self.assertIn(f'{toggle_name}: off', joined)

    def test_session_new_and_list(self) -> None:
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
            self.assertIn('session new:', joined)
            self.assertNotIn('error:', joined)

    def test_permission_mode_validation(self) -> None:
        valid_modes = [
            'read-only',
            'workspace-write',
            'prompt',
            'allow',
            'danger-full-access',
        ]
        for mode in valid_modes:
            with self.subTest(mode=mode):
                output: list[str] = []
                with tempfile.TemporaryDirectory() as tmp:
                    tui = TeaAgentTUI(
                        root=tmp,
                        input_fn=lambda _p: '',
                        output_fn=output.append,
                    )
                    tui.handle_command(f'permission {mode}')
                    joined = '\n'.join(output)
                    self.assertIn('permission:', joined)

        output = []
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui.handle_command('permission invalid-mode')
            joined = '\n'.join(output)
            self.assertIn('error:', joined)

    def test_pin_file_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'test.txt').write_text('hello', encoding='utf-8')
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui.handle_command('pin test.txt')
            tui.handle_command('pinned')
            tui.handle_command('unpin test.txt')
            joined = '\n'.join(output)
            self.assertIn('pinned: test.txt', joined)
            self.assertIn('unpinned: test.txt', joined)

    def test_compact_available(self) -> None:
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui.handle_command('compact')
            joined = '\n'.join(output)
            self.assertIn('compact:', joined)

    def test_daily_without_adapter(self) -> None:
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
            self.assertIn('daily:', joined)

    def test_unknown_command_shows_error(self) -> None:
        output: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui.handle_command('nonexistent_command_xyz')
            joined = '\n'.join(output)
            self.assertIn('error:', joined)

    def test_split_pane_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
            )
            result = tui._should_use_split_pane()
            self.assertIsInstance(result, bool)

    def test_state_panel_no_error(self) -> None:
        """Printing state panel should not throw."""
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _p: '',
                output_fn=output.append,
            )
            tui._print_state_panel()


if __name__ == '__main__':
    unittest.main()
