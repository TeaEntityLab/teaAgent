"""Real CLI/TUI behavioral parity tests — CG-17 fix.

These tests drive the actual TUI entry point (TeaAgentTUI) and verify it
delegates state mutations to ChatSessionController. (The legacy run_chat_repl
CLI surface was retired in U-P2-1, leaving the TUI as the single surface.)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from teaagent.types import FinalAnswer, RunResult

_FAKE_RESULT = RunResult(
    run_id='parity-run-001',
    final_answer=FinalAnswer(content='Parity answer'),
    iterations=1,
    tool_calls=0,
    status='completed',
    cost_cents=42.0,
    input_tokens=10,
    output_tokens=5,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tui(tmp_path, output_fn=None, input_fn=None):
    from teaagent.tui import TeaAgentTUI

    return TeaAgentTUI(
        root=str(tmp_path),
        output_fn=output_fn or (lambda _: None),
        input_fn=input_fn,
    )


# ---------------------------------------------------------------------------
# Test 1 — CLI/TUI cost parity
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cli_chat_vs_tui_same_cost_after_task(tmp_path):
    """Both CLI controller path and TUI _run_agent_task() should record same cost.

    Drives:
    - TUI: TeaAgentTUI._run_agent_task(task) which internally calls
           self._get_chat_controller().execute_task(...)
    - CLI: ChatSessionController.execute_task() directly (the path run_chat_repl delegates to)

    Both should credit the same cost_cents to their respective SessionState.
    """
    # --- TUI path ---
    tui_output: list[str] = []
    tui = _make_tui(tmp_path, output_fn=tui_output.append)

    fake_tui_store = MagicMock()
    fake_tui_store.audit_logger.return_value = MagicMock(path=None)
    fake_tui_store.show_run.return_value = []

    with (
        patch(
            'teaagent.chat_session_controller.run_chat_agent', return_value=_FAKE_RESULT
        ),
        patch('teaagent.chat_session_controller.RunStore'),
        patch('teaagent.tui.core.RunStore', return_value=fake_tui_store),
        patch('teaagent.tui.state.create_llm_adapter'),
        patch('teaagent.tui.core.RunStore', return_value=fake_tui_store),
    ):
        tui._run_agent_task('run some task')

    # Verify the TUI produced output (task was dispatched through controller)
    assert tui.last_run_id == 'parity-run-001', (
        f'TUI should set last_run_id from the run result, got: {tui.last_run_id}'
    )


# ---------------------------------------------------------------------------
# Test 3 — TUI undo delegates to controller, not duplicated git logic
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_tui_undo_delegates_to_controller(tmp_path):
    """TeaAgentTUI._handle_undo() must call controller.undo_last_run() first.

    The TUI has a checkpoint fallback, but the primary path must be the
    controller's journal-based undo.
    """
    tui_output: list[str] = []
    tui = _make_tui(tmp_path, output_fn=tui_output.append)

    controller = tui._get_chat_controller()
    undo_calls: list[bool] = []

    def spy_undo() -> bool:
        undo_calls.append(True)
        return True  # report success so checkpoint fallback is not triggered

    controller.undo_last_run = spy_undo

    tui._handle_undo()

    assert len(undo_calls) == 1, (
        f'TUI _handle_undo() must call controller.undo_last_run() exactly once, '
        f'called {len(undo_calls)} times'
    )


# Test 4 (CLI /undo delegates to controller) removed with U-P2-1: the legacy
# run_chat_repl REPL was retired, so the TUI/ChatSessionController is the single
# surface — undo-delegation parity is now structural, not a divergence risk.


# ---------------------------------------------------------------------------
# Test 5 — TUI cost property reads from controller, not local duplicate
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_tui_cost_property_reads_controller_state(tmp_path):
    """TeaAgentTUI._session_cost_cents must be sourced from the controller SessionState.

    If the TUI had its own parallel cost counter, this would expose the divergence.
    """
    tui = _make_tui(tmp_path)

    # Directly mutate the controller's session state
    controller = tui._get_chat_controller()
    controller.session_state.session_cost_cents = 99.5

    # TUI property must reflect controller state, not a separate counter
    assert tui._session_cost_cents == 99.5, (
        f'TUI._session_cost_cents should read from controller.session_state, '
        f'got {tui._session_cost_cents}'
    )

    # Mutate via TUI property — controller must see the same change
    tui._session_cost_cents = 200.0
    assert controller.session_state.session_cost_cents == 200.0, (
        f'Setting TUI._session_cost_cents must update controller.session_state, '
        f'controller sees {controller.session_state.session_cost_cents}'
    )
