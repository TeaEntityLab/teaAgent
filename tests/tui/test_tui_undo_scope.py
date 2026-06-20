"""U-P2-3: TUI undo-scope divergence fix tests.

The TUI ``/undo`` must match the CLI ``agent undo`` journal-first scope:
  - journal undo via ``ChatSessionController.undo_last_run()`` (scoped to the
    latest run with an undo journal), and
  - NO global git-stash checkpoint fallback (which restores files outside the
    journal scope and diverges from the CLI).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from teaagent.tui import TeaAgentTUI


def _make_tui(output: list[str]) -> TeaAgentTUI:
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    controller = MagicMock()
    controller.get_session_cost.return_value = 0.0
    controller.session_state.session_cost_cents = 0.0
    tui._chat_controller = controller
    return tui


def test_undo_journal_success_wording() -> None:
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = True

    tui._handle_undo()

    joined = ' '.join(output)
    assert 'journal undo completed' in joined


def test_undo_no_journal_reports_nothing_to_undo() -> None:
    """When no undo journal exists, the TUI reports nothing-to-undo (CLI parity)."""
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = False

    tui._handle_undo()

    joined = ' '.join(output)
    assert 'nothing to undo' in joined
    assert 'no undo journal' in joined


def test_undo_does_not_fall_back_to_global_checkpoint() -> None:
    """The global git-stash checkpoint fallback must be removed (journal-first scope)."""
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = False

    with patch.object(tui, '_restore_checkpoint') as mock_restore:
        tui._handle_undo()

        mock_restore.assert_not_called()

    joined = ' '.join(output)
    assert 'checkpoint restore' not in joined
    assert 'git-level restore' not in joined


def test_undo_does_not_mention_checkpoint_fallback_in_nothing_wording() -> None:
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = False

    tui._handle_undo()

    joined = ' '.join(output)
    # The old wording mentioned "no undo journal or checkpoint"; the new
    # journal-first wording must not reference checkpoints.
    assert 'or checkpoint' not in joined


def test_undo_command_path_via_handle_command() -> None:
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = False

    with patch.object(tui, '_restore_checkpoint') as mock_restore:
        tui.handle_command('undo')

        mock_restore.assert_not_called()

    joined = ' '.join(output)
    assert 'nothing to undo' in joined


def test_undo_slash_alias_via_handle_command() -> None:
    output: list[str] = []
    tui = _make_tui(output)
    tui._chat_controller.undo_last_run.return_value = True

    tui.handle_command('/undo')

    tui._chat_controller.undo_last_run.assert_called_once()
    joined = ' '.join(output)
    assert 'journal undo completed' in joined
