"""Tests for TUI split-screen layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.tui import TeaAgentTUI


def test_split_pane_detection_large_terminal(monkeypatch) -> None:
    """Test that split-pane is enabled for large terminals."""
    tui = TeaAgentTUI(root='.')

    # Mock terminal size to 120x30
    def mock_get_terminal_size():
        return (120, 30)

    import shutil
    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size)

    assert tui._should_use_split_pane() is True


def test_split_pane_detection_small_terminal(monkeypatch) -> None:
    """Test that split-pane is disabled for small terminals."""
    tui = TeaAgentTUI(root='.')

    # Mock terminal size to 80x24
    def mock_get_terminal_size():
        return (80, 24)

    import shutil
    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size)

    assert tui._should_use_split_pane() is False


def test_split_pane_detection_error_handling(monkeypatch) -> None:
    """Test that split-pane is disabled when terminal size cannot be determined."""
    tui = TeaAgentTUI(root='.')

    # Mock terminal size to raise error
    def mock_get_terminal_size():
        raise OSError("Cannot determine terminal size")

    import shutil
    monkeypatch.setattr(shutil, 'get_terminal_size', mock_get_terminal_size)

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
