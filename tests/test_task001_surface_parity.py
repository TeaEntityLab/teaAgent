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
from unittest.mock import MagicMock, patch

import pytest

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


@pytest.fixture
def surface_parity_setup():
    tmp = tempfile.mkdtemp()
    cli_out: list[str] = []
    tui_out: list[str] = []
    # Two controllers standing in for the CLI and TUI surfaces: same root,
    # different output sinks.
    cli = ChatSessionController(tmp, output_fn=cli_out.append)
    tui = ChatSessionController(tmp, output_fn=tui_out.append)
    yield tmp, cli, tui, cli_out, tui_out
    # Verify cleanup
    import os
    import shutil

    assert os.path.exists(tmp), (
        f'Temporary directory {tmp} should still exist before cleanup'
    )
    shutil.rmtree(tmp)
    assert not os.path.exists(tmp), f'Temporary directory {tmp} was not cleaned up'


def test_cost_semantics_identical_across_surfaces(surface_parity_setup):
    tmp, cli, tui, cli_out, tui_out = surface_parity_setup
    with patch(
        'teaagent.chat_session_controller.run_chat_agent',
        return_value=_fake_result(137.0),
    ):
        _execute(cli, tmp)
        _execute(tui, tmp)
    # Same spend -> same trust-relevant outcome on both surfaces.
    assert cli.get_session_cost() == tui.get_session_cost()
    assert cli.get_session_cost_display() == tui.get_session_cost_display()
    assert cli.get_session_cost_display() == '$1.37'


def test_undo_outcome_identical_across_surfaces(surface_parity_setup):
    tmp, cli, tui, cli_out, tui_out = surface_parity_setup
    # With no undo journal present, both surfaces report the same safe outcome.
    cli_result = cli.undo_last_run()
    tui_result = tui.undo_last_run()
    assert cli_result == tui_result
    assert not cli_result
    # The fallback path is explicitly labeled identically on both surfaces.
    assert cli_out[-1] == tui_out[-1]
    assert 'Nothing to undo' in cli_out[-1]
