"""P0-D-001: Explicit root priority — --root always wins over saved state."""

from __future__ import annotations

import unittest
from pathlib import Path

from teaagent.tui import TeaAgentTUI
from teaagent.types import PermissionMode


class TeaAgentTUITestHelper(TeaAgentTUI):
    """Test helper that bypasses real state file I/O."""

    def inject_state(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self.provider = data.get('provider', self.provider)
        self.model = data.get('model', self.model)
        if not self._root_explicit:
            saved_root = data.get('root')
            if saved_root:
                self.root = Path(saved_root).resolve()
        mode_val = data.get('permission_mode')
        if mode_val:
            self.permission_mode = PermissionMode(mode_val)
        self.allow_destructive = data.get('allow_destructive', self.allow_destructive)


class TestExplicitRootOverridesSavedState(unittest.TestCase):
    def test_explicit_root_overrides_saved_state(self) -> None:
        explicit_root = '/tmp/test-explicit-root'
        saved_root = '/tmp/saved-state-root'

        tui = TeaAgentTUITestHelper(root=explicit_root)
        tui._root_explicit = True
        tui.inject_state({'root': saved_root, 'provider': 'gpt'})

        self.assertEqual(
            str(tui.root),
            str(Path(explicit_root).resolve()),
            'Explicit root must not be overridden by saved state',
        )

    def test_saved_root_cannot_override_explicit_root(self) -> None:
        explicit_root = '/tmp/test-explicit-root-2'
        saved_root = '/tmp/saved-root-2'

        tui_default = TeaAgentTUITestHelper(root='.')
        tui_default._root_explicit = False
        tui_default.inject_state({'root': saved_root, 'provider': 'gpt'})
        self.assertEqual(
            str(tui_default.root),
            str(Path(saved_root).resolve()),
            'Without explicit root, saved state root should be restored',
        )

        tui_explicit = TeaAgentTUITestHelper(root=explicit_root)
        tui_explicit._root_explicit = True
        tui_explicit.inject_state({'root': saved_root, 'provider': 'gpt'})
        self.assertEqual(
            str(tui_explicit.root),
            str(Path(explicit_root).resolve()),
            'Explicit root must not be overridden by saved state root',
        )

    def test_tui_root_command_sets_explicit_flag(self) -> None:
        tui = TeaAgentTUITestHelper(root='/tmp/original-root')

        from teaagent.tui._commands import _cmd_root

        _cmd_root(tui, ['/tmp/new-root'])
        self.assertTrue(
            tui._root_explicit,
            'TUI root command must set _root_explicit=True',
        )
        self.assertEqual(
            str(tui.root),
            str(Path('/tmp/new-root').resolve()),
        )

    def test_explicit_root_persists_across_state_load(self) -> None:
        tui = TeaAgentTUITestHelper(root='/tmp/explicit-root-3')
        tui._root_explicit = True

        for saved_root in ['/tmp/other-1', '/tmp/other-2']:
            tui.inject_state({'root': saved_root, 'provider': 'gpt'})

        self.assertEqual(
            str(tui.root),
            str(Path('/tmp/explicit-root-3').resolve()),
            'Explicit root must persist across multiple state loads',
        )


if __name__ == '__main__':
    unittest.main()
