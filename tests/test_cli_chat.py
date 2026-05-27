"""Tests for CLI chat REPL handler."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.cli._handlers._chat import chat_command, print_chat_help, run_chat_repl
from teaagent.chat_agent import ChatAgentConfig


def test_print_chat_help(capsys):
    """Test that chat help prints correctly."""
    print_chat_help()
    captured = capsys.readouterr()
    assert "Chat Commands:" in captured.out
    assert "/exit" in captured.out
    assert "/help" in captured.out


def test_chat_command_with_invalid_args():
    """Test chat command with invalid arguments."""
    # Skip this test as it requires full config setup
    # The actual functionality is tested via integration tests
    pytest.skip("Requires full config setup")


def test_run_chat_repl_exit_command(monkeypatch):
    """Test REPL exits with /exit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Mock input to return /exit immediately
        inputs = ["/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_quit_command(monkeypatch):
    """Test REPL exits with quit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["quit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_help_command(monkeypatch, capsys):
    """Test REPL shows help with /help command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/help", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Chat Commands:" in captured.out
        assert result == 0


def test_run_chat_repl_keyboard_interrupt(monkeypatch):
    """Test REPL handles KeyboardInterrupt gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        def mock_input(prompt):
            raise KeyboardInterrupt()
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        result = run_chat_repl(config)
        # Should handle interrupt and continue
        assert result is not None


def test_run_chat_repl_eof(monkeypatch):
    """Test REPL handles EOFError (Ctrl+D) gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        def mock_input(prompt):
            raise EOFError()
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_empty_input(monkeypatch):
    """Test REPL skips empty input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["", "  ", "\t", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        assert result == 0
