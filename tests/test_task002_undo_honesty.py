"""TASK-002 verify-first: undo wording and behavior honesty.

Acceptance criterion (roadmap-work-items-2026-06-04, TASK-002):
"Separate journal-based undo from checkpoint restore in both code and docs" so
"user can tell which undo path is used before they run it."

The information needed to know the path before running exists in two places:
- the cockpit reports journal and checkpoint availability as *separate* signals
  (``RecoverableState.has_undo_journal`` vs ``has_checkpoint``);
- ``undo`` is deterministically journal-first (documented in help text), so the
  selected path is derivable from the availability signals.

After running, the completion wording names the actual path used. These tests
lock that honest separation so a future change cannot collapse the two undo
paths into one ambiguous message.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from teaagent.cockpit import RecoverableState
from teaagent.tui import TeaAgentTUI


class UndoHonestyWordingTests(unittest.TestCase):
    def _tui(self, output: list[str]) -> TeaAgentTUI:
        return TeaAgentTUI(
            root=Path(tempfile.mkdtemp()),
            input_fn=lambda _p: '',
            output_fn=output.append,
        )

    def test_journal_path_wording_names_journal(self) -> None:
        output: list[str] = []
        tui = self._tui(output)
        with patch.object(
            tui._get_chat_controller(), 'undo_last_run', return_value=True
        ):
            tui._handle_undo()
        self.assertIn('journal', output[-1].lower())
        self.assertNotIn('checkpoint', output[-1].lower())

    def test_checkpoint_path_wording_names_checkpoint(self) -> None:
        output: list[str] = []
        tui = self._tui(output)
        with (
            patch.object(
                tui._get_chat_controller(), 'undo_last_run', return_value=False
            ),
            patch.object(tui, '_restore_checkpoint', return_value=True),
        ):
            tui._handle_undo()
        self.assertIn('checkpoint', output[-1].lower())

    def test_nothing_to_undo_is_explicit(self) -> None:
        output: list[str] = []
        tui = self._tui(output)
        with (
            patch.object(
                tui._get_chat_controller(), 'undo_last_run', return_value=False
            ),
            patch.object(tui, '_restore_checkpoint', return_value=False),
        ):
            tui._handle_undo()
        self.assertIn('nothing to undo', output[-1].lower())


class RecoverableStateSeparationTests(unittest.TestCase):
    def test_journal_and_checkpoint_are_independent_signals(self) -> None:
        state = RecoverableState(has_undo_journal=True, has_checkpoint=False)
        self.assertTrue(state.has_undo_journal)
        self.assertFalse(state.has_checkpoint)

    def test_state_exposes_both_recovery_signals(self) -> None:
        # The two recovery paths must remain separately representable so the
        # cockpit can show which one undo will use before it runs.
        state = RecoverableState()
        self.assertIn('has_undo_journal', vars(state))
        self.assertIn('has_checkpoint', vars(state))


if __name__ == '__main__':
    unittest.main()
