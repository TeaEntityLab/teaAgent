"""TASK-003 verify-first: cost truth on the daily surfaces.

Acceptance criterion (roadmap-work-items-2026-06-04, TASK-003):
"cost reflects actual run spend after a real task execution" and the daily
surfaces "never show a fake zero or stale local state".

These tests pin the ChatSessionController cost contract directly (the source of
truth that both CLI and TUI read), independent of TUI rendering:

- a run that produces non-zero spend is reflected in the session cost;
- the formatted display never reports ``$0.00`` after real spend;
- repeated runs accumulate additively (no stale/overwrite).
"""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from teaagent.chat_session_controller import ChatSessionController
from teaagent.run_undo import UndoJournal
from teaagent.types import AuditLogger


def _fake_result(cost_cents: float, run_id: str = 'run-1') -> MagicMock:
    return MagicMock(
        run_id=run_id,
        status='completed',
        cost_cents=cost_cents,
        final_answer=MagicMock(content='ok'),
        error_message=None,
        metadata={},
    )


def _run(controller: ChatSessionController, tmp: str) -> None:
    # audit with path=None skips RunStore persistence; empty journal skips save.
    controller.execute_task(
        'do a thing',
        config=MagicMock(model='gpt/x'),
        adapter=object(),
        audit=AuditLogger(),
        undo_journal=UndoJournal(tmp),
        emit_answer=False,
    )


@pytest.fixture
def cost_truth_controller():
    tmp = tempfile.mkdtemp()
    controller = ChatSessionController(tmp, output_fn=lambda _m: None)
    yield tmp, controller
    # Verify cleanup
    import os
    import shutil

    assert os.path.exists(tmp), (
        f'Temporary directory {tmp} should still exist before cleanup'
    )
    shutil.rmtree(tmp)
    assert not os.path.exists(tmp), f'Temporary directory {tmp} was not cleaned up'


def test_nonzero_spend_is_reflected(cost_truth_controller):
    tmp, controller = cost_truth_controller
    with patch(
        'teaagent.chat_session_controller.run_chat_agent',
        return_value=_fake_result(150.0),
    ):
        _run(controller, tmp)
    assert controller.get_session_cost() == 150.0


def test_no_fake_zero_after_real_spend(cost_truth_controller):
    tmp, controller = cost_truth_controller
    with patch(
        'teaagent.chat_session_controller.run_chat_agent',
        return_value=_fake_result(1.0),
    ):
        _run(controller, tmp)
    # The headline guarded behaviour: after real spend the display must not
    # report a fake zero.
    assert controller.get_session_cost_display() != '$0.00'
    assert controller.get_session_cost_display() == '$0.01'


def test_repeated_runs_accumulate(cost_truth_controller):
    tmp, controller = cost_truth_controller
    with patch('teaagent.chat_session_controller.run_chat_agent') as mock_run:
        mock_run.return_value = _fake_result(75.0, 'run-1')
        _run(controller, tmp)
        mock_run.return_value = _fake_result(25.0, 'run-2')
        _run(controller, tmp)
    assert controller.get_session_cost() == 100.0
    assert controller.get_session_cost_display() == '$1.00'


def test_zero_cost_run_is_honest_zero(cost_truth_controller):
    tmp, controller = cost_truth_controller
    # A genuinely free run reports $0.00 — that is honest, not a fake zero.
    with patch(
        'teaagent.chat_session_controller.run_chat_agent',
        return_value=_fake_result(0.0),
    ):
        _run(controller, tmp)
    assert controller.get_session_cost_display() == '$0.00'
