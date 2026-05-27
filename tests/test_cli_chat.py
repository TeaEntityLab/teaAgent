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
        
        inputs = ["/exit"]
        call_count = [0]
        
        def mock_input(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt()
            return inputs.pop(0)
        
        monkeypatch.setattr("builtins.input", mock_input)
        
        result = run_chat_repl(config)
        # Should handle interrupt and continue to exit
        assert result == 0


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


def test_run_chat_repl_context_command(monkeypatch, capsys):
    """Test REPL /context command shows targeted files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/context", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "No files currently targeted" in captured.out
        assert result == 0


def test_run_chat_repl_add_command(monkeypatch, capsys):
    """Test REPL /add command adds files to context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Create a test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('test')")
        
        inputs = ["/add test.py", "/context", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Added to context" in captured.out
        assert "test.py" in captured.out
        assert result == 0


def test_run_chat_repl_drop_command(monkeypatch, capsys):
    """Test REPL /drop command removes files from context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Create a test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('test')")
        
        inputs = ["/add test.py", "/drop test.py", "/context", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Removed from context" in captured.out
        assert "No files currently targeted" in captured.out
        assert result == 0


def test_run_chat_repl_cost_command(monkeypatch, capsys):
    """Test REPL /cost command shows session cost."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/cost", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Session cost" in captured.out
        assert result == 0


def test_run_chat_repl_compact_command(monkeypatch, capsys):
    """Test REPL /compact command shows compaction info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/compact", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Compaction complete" in captured.out
        assert result == 0


def test_run_chat_repl_provider_command(monkeypatch, capsys):
    """Test REPL /provider command switches provider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/provider claude", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Provider switched" in captured.out
        assert result == 0


def test_run_chat_repl_model_command(monkeypatch, capsys):
    """Test REPL /model command switches model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/model claude-3-5-sonnet", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Model switched" in captured.out
        assert result == 0


def test_run_chat_repl_effort_command(monkeypatch, capsys):
    """Test REPL /effort command sets effort level."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/effort low", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Effort level set to: low" in captured.out
        assert "Budget limit" in captured.out
        assert result == 0


def test_run_chat_repl_budget_command(monkeypatch, capsys):
    """Test REPL /budget command shows budget status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        inputs = ["/budget", "/exit"]
        monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
        
        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert "Effort level" in captured.out
        assert "Budget limit" in captured.out
        assert "Session cost" in captured.out
        assert result == 0
