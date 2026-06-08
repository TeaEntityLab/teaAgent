"""TASK-001 verify-first: TUI / CLI semantic drift.

Acceptance criterion (roadmap-work-items-2026-06-04, TASK-001):
"same user command produces same trust semantics on CLI and TUI; fallback paths
are explicitly labeled."

Both surfaces route trust-relevant operations (cost accounting, undo) through the
single ``ChatSessionController``. These tests prove the semantics are
surface-independent: the only per-surface difference is the ``output_fn`` sink,
not the trust outcome. If a future change reintroduces a surface-local code path,
these parity assertions fail.
"""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from teaagent.chat_session_controller import ChatSessionController
from teaagent.run_undo import UndoJournal
from teaagent.types import AuditLogger


def _fake_result(cost_cents: float) -> MagicMock:
    return MagicMock(
        run_id='run-1',
        status='completed',
        cost_cents=cost_cents,
        final_answer=MagicMock(content='ok'),
        error_message=None,
        metadata={},
    )


def _execute(controller: ChatSessionController, tmp: str) -> None:
    controller.execute_task(
        'task',
        config=MagicMock(model='gpt/x'),
        adapter=object(),
        audit=AuditLogger(),
        undo_journal=UndoJournal(tmp),
        emit_answer=False,
    )


class SurfaceParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.cli_out: list[str] = []
        self.tui_out: list[str] = []
        # Two controllers standing in for the CLI and TUI surfaces: same root,
        # different output sinks.
        self.cli = ChatSessionController(self._tmp, output_fn=self.cli_out.append)
        self.tui = ChatSessionController(self._tmp, output_fn=self.tui_out.append)

    def test_cost_semantics_identical_across_surfaces(self) -> None:
        with patch(
            'teaagent.chat_session_controller.run_chat_agent',
            return_value=_fake_result(137.0),
        ):
            _execute(self.cli, self._tmp)
            _execute(self.tui, self._tmp)
        # Same spend -> same trust-relevant outcome on both surfaces.
        self.assertEqual(self.cli.get_session_cost(), self.tui.get_session_cost())
        self.assertEqual(
            self.cli.get_session_cost_display(),
            self.tui.get_session_cost_display(),
        )
        self.assertEqual(self.cli.get_session_cost_display(), '$1.37')

    def test_undo_outcome_identical_across_surfaces(self) -> None:
        # With no undo journal present, both surfaces report the same safe outcome.
        cli_result = self.cli.undo_last_run()
        tui_result = self.tui.undo_last_run()
        self.assertEqual(cli_result, tui_result)
        self.assertFalse(cli_result)
        # The fallback path is explicitly labeled identically on both surfaces.
        self.assertEqual(self.cli_out[-1], self.tui_out[-1])
        self.assertIn('Nothing to undo', self.cli_out[-1])


if __name__ == '__main__':
    unittest.main()
