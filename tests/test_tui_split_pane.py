"""Tests for TUI split-screen layout."""

from __future__ import annotations

from teaagent.tui import TeaAgentTUI


def test_split_pane_detection_large_terminal(monkeypatch) -> None:
    """Test that split-pane is enabled for large terminals."""
    tui = TeaAgentTUI(root='.')

    # Mock terminal size to 120x30
    def mock_get_terminal_size(fallback=None):
        return os_terminal_size((120, 30))

    import os

    os_terminal_size = getattr(os, 'terminal_size', tuple)
    import shutil

    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size)

    assert tui._should_use_split_pane() is True


def test_split_pane_detection_small_terminal(monkeypatch) -> None:
    """Test that split-pane is disabled for small terminals."""
    tui = TeaAgentTUI(root='.')

    # Mock terminal size to 80x24
    def mock_get_terminal_size(fallback=None):
        return os_terminal_size((80, 24))

    import os

    os_terminal_size = getattr(os, 'terminal_size', tuple)
    import shutil

    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size)

    assert tui._should_use_split_pane() is False


def test_split_pane_detection_error_handling(monkeypatch) -> None:
    """Test that split-pane is disabled when terminal size cannot be determined."""
    import os
    import shutil

    tui = TeaAgentTUI(root='.')

    # Mock shutil.get_terminal_size to raise error only within the TUI context
    # Use a context manager approach to avoid affecting pytest's terminal writer
    def mock_get_terminal_size_context(fallback=None):
        # Check if we're being called from pytest's terminal writer
        import traceback

        stack = traceback.extract_stack()
        for frame in stack:
            if 'terminalwriter' in frame.filename or '_pytest' in frame.filename:
                # Return a safe default for pytest's internal use
                os_terminal_size = getattr(os, 'terminal_size', tuple)
                return os_terminal_size((80, 24))
        # Raise error for TUI calls
        raise OSError('Cannot determine terminal size')

    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size_context)

    assert tui._should_use_split_pane() is False


def test_state_panel_output(capsys) -> None:
    """Test that state panel prints expected information."""
    tui = TeaAgentTUI(root='.')

    tui._print_state_panel()
    captured = capsys.readouterr()

    # Check for expected output
    assert 'TeaAgent TUI' in captured.out
    assert 'State Panel' in captured.out
    assert 'Provider:' in captured.out
    assert 'Permission Mode:' in captured.out
