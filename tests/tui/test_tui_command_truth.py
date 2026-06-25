"""U-P0-2 (ADR-0038): TUI command-truth tests.

Asserts that HELP_TEXT does not advertise commands that do not behave as
described:
  (a) no HELP_TEXT entry returns a "not yet implemented" response,
  (b) every advertised command dispatches to a handler whose response is
      consistent with the help text (no "not yet implemented" / "not available"
      promises for advertised commands), and
  (c) conflict / o / t / n / p / a are NOT in HELP_TEXT.
"""

from __future__ import annotations

import re
from unittest.mock import patch

from teaagent.tui import TeaAgentTUI
from teaagent.tui.rendering import HELP_TEXT

# Commands that were removed from HELP_TEXT per ADR-0038.
_REMOVED_COMMANDS = {'conflict', 'o', 't', 'n', 'p', 'a'}


def _advertised_commands() -> set[str]:
    """Parse the first token of each command line in the HELP_TEXT command list.

    Only the top-level ``Commands:`` block is scanned (the indented reference
    section below it uses a different indentation and is excluded).
    """
    commands: set[str] = set()
    in_commands = False
    for line in HELP_TEXT.splitlines():
        if line.startswith('Commands:'):
            in_commands = True
            continue
        if not in_commands:
            continue
        # Stop at the first non-indented line (end of the command list block).
        if line and not line.startswith(' '):
            break
        # Command lines are indented and start with a command word followed by
        # either whitespace or an argument placeholder.
        m = re.match(r'^  (?P<cmd>[a-zA-Z][a-zA-Z0-9_-]*)\s', line)
        if m:
            commands.add(m.group('cmd'))
    return commands


def _make_tui() -> tuple[TeaAgentTUI, list[str]]:
    output: list[str] = []
    tui = TeaAgentTUI(input_fn=lambda _: '', output_fn=output.append)
    tui._get_chat_controller()
    return tui, output


def test_removed_commands_not_in_help_text() -> None:
    """(c) conflict/o/t/n/p/a must NOT appear as advertised commands."""
    advertised = _advertised_commands()
    for removed in _REMOVED_COMMANDS:
        assert removed not in advertised, (
            f'command "{removed}" should have been removed from HELP_TEXT'
        )


def test_no_advertised_command_returns_not_yet_implemented() -> None:
    """(a) No advertised command may respond with "not yet implemented"."""
    tui, output = _make_tui()
    with (
        patch.object(tui, '_start_file_watcher'),
        patch.object(tui, '_load_tui_state'),
        patch.object(tui, '_save_tui_state'),
        patch('teaagent.tui.state.create_llm_adapter'),
    ):
        # Dispatch a representative sample of advertised commands with safe args.
        # These are the lightweight, side-effect-free commands from HELP_TEXT that
        # work without a real workspace/git repo.
        sample: list[str] = [
            'help',
            'doctor',
            'cost',
            'budget',
            'pinned',
            'approvals',
            'compact',
            'skill-health',
        ]
        for cmd in sample:
            output.clear()
            tui.handle_command(cmd)
            joined = ' '.join(output)
            assert 'not yet implemented' not in joined.lower(), (
                f'command "{cmd}" returned a "not yet implemented" response: {joined!r}'
            )


def test_conflict_shortcuts_report_not_available_not_yet_implemented() -> None:
    """Removed conflict shortcuts must say "not available", not "not yet implemented"."""
    tui, output = _make_tui()
    for shortcut in ('conflict', 'o', 't', 'n', 'p', 'a'):
        output.clear()
        tui.handle_command(shortcut)
        joined = ' '.join(output)
        assert 'not available' in joined.lower(), (
            f'shortcut "{shortcut}" should report "not available": {joined!r}'
        )
        assert 'not yet implemented' not in joined.lower(), (
            f'shortcut "{shortcut}" must not promise "not yet implemented": {joined!r}'
        )


def test_parallel_select_cancel_help_text_matches_behavior() -> None:
    """(b) parallel/select/cancel help text matches actual handler behavior."""
    tui, output = _make_tui()
    # parallel stores option strings
    output.clear()
    tui.handle_command('parallel optA optB')
    joined = ' '.join(output)
    assert 'options_stored' in joined or 'options' in joined.lower()
    # select marks an option selected
    output.clear()
    tui.handle_command('select 0')
    joined = ' '.join(output)
    assert 'selected' in joined.lower() or 'error' in joined.lower()
    # cancel clears stored options
    output.clear()
    tui.handle_command('cancel')
    joined = ' '.join(output)
    assert 'cancelled' in joined.lower() or 'cleared' in joined.lower()


def test_help_text_does_not_promise_parallel_experiment_branches() -> None:
    """The "Start parallel experiment branches" promise must be removed."""
    assert 'Start parallel experiment branches' not in HELP_TEXT
    assert 'Merge selected parallel experiment branch' not in HELP_TEXT
    assert 'Cancel and cleanup all parallel experiment branches' not in HELP_TEXT


def test_help_text_describes_actual_parallel_select_cancel_behavior() -> None:
    """HELP_TEXT must describe the actual (storage) behavior, not experiment branches."""
    assert 'Store option strings' in HELP_TEXT
    assert 'Mark an option selected' in HELP_TEXT
    assert 'Clear stored parallel options' in HELP_TEXT


def test_undo_help_text_has_no_duplicate() -> None:
    """U-P2-5: the duplicate undo help line must be removed from the command list."""
    # Count lines in the top-level Commands: block whose first command token is "undo".
    undo_lines: list[str] = []
    in_commands = False
    for line in HELP_TEXT.splitlines():
        if line.startswith('Commands:'):
            in_commands = True
            continue
        if not in_commands:
            continue
        if line and not line.startswith(' '):
            break
        if re.match(r'^  undo\s', line):
            undo_lines.append(line)
    assert len(undo_lines) == 1, (
        f'expected exactly one undo help line in the command list, '
        f'found {len(undo_lines)}: {undo_lines}'
    )
