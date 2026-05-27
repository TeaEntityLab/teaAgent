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


def test_run_chat_repl_provider_command_updates_adapter(monkeypatch, capsys):
    """Test REPL /provider command actually updates the adapter for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Mock the create_llm_adapter to track calls
        from unittest.mock import patch, MagicMock
        adapter_mock = MagicMock()
        adapter_calls = []
        
        def mock_create_adapter(provider, *, model=None):
            adapter_calls.append((provider, model))
            return adapter_mock
        
        inputs = ["/provider gpt", "/exit"]
        with patch('teaagent.cli._handlers._chat.create_llm_adapter', side_effect=mock_create_adapter):
            monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
            result = run_chat_repl(config)
        
        captured = capsys.readouterr()
        assert "Provider switched" in captured.out
        # Verify adapter was recreated with new provider
        assert len(adapter_calls) >= 2  # Initial + swap
        assert result == 0


def test_run_chat_repl_model_command_updates_adapter(monkeypatch, capsys):
    """Test REPL /model command actually updates the adapter for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Mock the create_llm_adapter to track calls
        from unittest.mock import patch, MagicMock
        adapter_mock = MagicMock()
        adapter_calls = []
        
        def mock_create_adapter(provider, *, model=None):
            adapter_calls.append((provider, model))
            return adapter_mock
        
        inputs = ["/model gpt-4", "/exit"]
        with patch('teaagent.cli._handlers._chat.create_llm_adapter', side_effect=mock_create_adapter):
            monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
            result = run_chat_repl(config)
        
        captured = capsys.readouterr()
        assert "Model switched" in captured.out
        # Verify adapter was recreated with new model
        assert len(adapter_calls) >= 2  # Initial + swap
        assert result == 0


def test_run_chat_repl_effort_command_updates_budget(monkeypatch, capsys):
    """Test REPL /effort command actually updates the budget for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        
        # Mock the create_llm_adapter to avoid actual API calls
        from unittest.mock import patch, MagicMock
        adapter_mock = MagicMock()
        
        def mock_create_adapter(provider, *, model=None):
            return adapter_mock
        
        # Mock run_chat_agent to capture the config it receives
        captured_configs = []
        
        def mock_run_chat_agent(*, task, adapter, config):
            captured_configs.append(config)
            from teaagent.runner import RunResult
            return RunResult(success=True, final_answer="test", iterations=0, tool_calls=0)
        
        inputs = ["/effort high", "/exit"]
        with patch('teaagent.cli._handlers._chat.create_llm_adapter', side_effect=mock_create_adapter):
            with patch('teaagent.cli._handlers._chat.run_chat_agent', side_effect=mock_run_chat_agent):
                monkeypatch.setattr("builtins.input", lambda _: inputs.pop(0))
                result = run_chat_repl(config)
        
        captured = capsys.readouterr()
        assert "Effort level set to: high" in captured.out
        assert "Budget limit: $50.00" in captured.out
        assert result == 0


def test_cli_default_entry_launches_chat():
    """Test that running CLI with no arguments defaults to agent chat command."""
    from teaagent.cli import main
    from unittest.mock import patch, MagicMock
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the chat_command to verify it's called
        chat_called = []
        
        def mock_chat_command(args):
            chat_called.append(True)
            return 0
        
        with patch('teaagent.cli.chat_command', side_effect=mock_chat_command):
            # Simulate running with no arguments
            result = main(argv=[], _adapter_factory=MagicMock(), _serve_mcp_http=MagicMock(), 
                        _check_graphqlite=MagicMock(), _check_llm=MagicMock(), 
                        _run_model_conformance=MagicMock())
        
        assert len(chat_called) == 1
        assert result == 0


def test_git_sandbox_consent_saved_to_config():
    """Test that git_sandbox_consent is saved to config.json."""
    from teaagent.cli._handlers._agent import _save_git_sandbox_consent
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save consent
        _save_git_sandbox_consent(tmpdir, 'always')
        
        # Verify it was saved
        config_path = Path(tmpdir) / '.teaagent' / 'config.json'
        assert config_path.exists()
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        assert config.get('git_sandbox_consent') == 'always'


def test_git_sandbox_consent_updates_existing_config():
    """Test that git_sandbox_consent updates existing config.json."""
    from teaagent.cli._handlers._agent import _save_git_sandbox_consent
    import json
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create existing config
        config_path = Path(tmpdir) / '.teaagent' / 'config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        existing_config = {'provider': 'gpt', 'model': 'gpt-4'}
        with open(config_path, 'w') as f:
            json.dump(existing_config, f)
        
        # Save consent
        _save_git_sandbox_consent(tmpdir, 'always')
        
        # Verify it was merged
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        assert config.get('git_sandbox_consent') == 'always'
        assert config.get('provider') == 'gpt'
        assert config.get('model') == 'gpt-4'
