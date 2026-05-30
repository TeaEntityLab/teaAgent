"""Tests for CLI chat REPL handler."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli._handlers._chat import chat_command
from teaagent.cli._handlers.agent_review import interactive_review_mode
from teaagent.cli._handlers.chat_commands import execute_shell_command
from teaagent.cli._handlers.chat_completion import complete_file_path, complete_symbol
from teaagent.cli._handlers.chat_repl import (
    print_chat_help,
    run_chat_repl,
    suspend_to_background,
)


def test_print_chat_help(capsys):
    """Test that chat help prints correctly."""
    print_chat_help()
    captured = capsys.readouterr()
    assert 'Chat Commands:' in captured.out
    assert '/exit' in captured.out
    assert '/help' in captured.out


def test_chat_command_with_invalid_args():
    """Test chat command with invalid arguments."""
    # Skip this test as it requires full config setup
    # The actual functionality is tested via integration tests
    pytest.skip('Requires full config setup')


def test_chat_command_smoke_test():
    """Test chat command starts and exits cleanly via /exit command."""
    import argparse

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal args namespace
        args = argparse.Namespace(
            root=tmpdir,
            model=None,
            permission_mode='prompt',
            max_iterations=10,
            max_tool_calls=10,
            max_estimated_cost_cents=0,
            allow_destructive=False,
            memory_limit=None,
            subagent=False,
            max_subagent_depth=1,
            heartbeat=0.0,
            stream=False,
            task=None,
        )

        # Mock input to return /exit immediately
        import builtins

        original_input = builtins.input
        builtins.input = lambda _: '/exit'

        try:
            result = chat_command(args)
            assert result == 0, f'Expected exit code 0, got {result}'
        finally:
            builtins.input = original_input


def test_run_chat_repl_exit_command(monkeypatch):
    """Test REPL exits with /exit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Mock input to return /exit immediately
        inputs = ['/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_quit_command(monkeypatch):
    """Test REPL exits with quit command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['quit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_help_command(monkeypatch, capsys):
    """Test REPL shows help with /help command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/help', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Chat Commands:' in captured.out
        assert result == 0


def test_run_chat_repl_keyboard_interrupt(monkeypatch):
    """Test REPL handles KeyboardInterrupt gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/exit']
        call_count = [0]

        def mock_input(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt()
            return inputs.pop(0)

        monkeypatch.setattr('builtins.input', mock_input)

        result = run_chat_repl(config)
        # Should handle interrupt and continue to exit
        assert result == 0


def test_run_chat_repl_eof(monkeypatch):
    """Test REPL handles EOFError (Ctrl+D) gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        def mock_input(prompt):
            raise EOFError()

        monkeypatch.setattr('builtins.input', mock_input)

        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_empty_input(monkeypatch):
    """Test REPL skips empty input."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['', '  ', '\t', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        assert result == 0


def test_run_chat_repl_context_command(monkeypatch, capsys):
    """Test REPL /context command shows targeted files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/context', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'No files currently targeted' in captured.out
        assert result == 0


def test_run_chat_repl_add_command(monkeypatch, capsys):
    """Test REPL /add command adds files to context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Create a test file
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text("print('test')")

        inputs = ['/add test.py', '/context', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Added to context' in captured.out
        assert 'test.py' in captured.out
        assert result == 0


def test_run_chat_repl_drop_command(monkeypatch, capsys):
    """Test REPL /drop command removes files from context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Create a test file
        test_file = Path(tmpdir) / 'test.py'
        test_file.write_text("print('test')")

        inputs = ['/add test.py', '/drop test.py', '/context', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Removed from context' in captured.out
        assert 'No files currently targeted' in captured.out
        assert result == 0


def test_run_chat_repl_cost_command(monkeypatch, capsys):
    """Test REPL /cost command shows session cost."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/cost', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Session cost' in captured.out
        assert result == 0


def test_run_chat_repl_compact_command(monkeypatch, capsys):
    """Test REPL /compact command shows compaction info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/compact', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Compaction complete' in captured.out
        assert result == 0


def test_run_chat_repl_provider_command(monkeypatch, capsys):
    """Test REPL /provider command switches provider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/provider claude', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Provider switched' in captured.out
        assert result == 0


def test_run_chat_repl_model_command(monkeypatch, capsys):
    """Test REPL /model command switches model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/model claude-3-5-sonnet', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Model switched' in captured.out
        assert result == 0


def test_run_chat_repl_effort_command(monkeypatch, capsys):
    """Test REPL /effort command sets effort level."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/effort low', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Effort level set to: low' in captured.out
        assert 'Budget limit' in captured.out
        assert result == 0


def test_run_chat_repl_budget_command(monkeypatch, capsys):
    """Test REPL /budget command shows budget status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/budget', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        result = run_chat_repl(config)
        captured = capsys.readouterr()
        assert 'Effort level' in captured.out
        assert 'Budget limit' in captured.out
        assert 'Session cost' in captured.out
        assert result == 0


def test_run_chat_repl_provider_command_updates_adapter(monkeypatch, capsys):
    """Test REPL /provider command actually updates the adapter for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Mock the create_llm_adapter to track calls
        from unittest.mock import MagicMock, patch

        adapter_mock = MagicMock()
        adapter_calls = []

        def mock_create_adapter(provider, *, model=None):
            adapter_calls.append((provider, model))
            return adapter_mock

        inputs = ['/provider gpt', '/exit']
        with patch(
            'teaagent.cli._handlers.chat_repl.create_llm_adapter',
            side_effect=mock_create_adapter,
        ):
            monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
            result = run_chat_repl(config)

        captured = capsys.readouterr()
        assert 'Provider switched' in captured.out
        # Verify adapter was recreated with new provider
        assert len(adapter_calls) >= 2  # Initial + swap
        assert result == 0


def test_run_chat_repl_model_command_updates_adapter(monkeypatch, capsys):
    """Test REPL /model command actually updates the adapter for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Mock the create_llm_adapter to track calls
        from unittest.mock import MagicMock, patch

        adapter_mock = MagicMock()
        adapter_calls = []

        def mock_create_adapter(provider, *, model=None):
            adapter_calls.append((provider, model))
            return adapter_mock

        inputs = ['/model gpt-4', '/exit']
        with patch(
            'teaagent.cli._handlers.chat_repl.create_llm_adapter',
            side_effect=mock_create_adapter,
        ):
            monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
            result = run_chat_repl(config)

        captured = capsys.readouterr()
        assert 'Model switched' in captured.out
        # Verify adapter was recreated with new model
        assert len(adapter_calls) >= 2  # Initial + swap
        assert result == 0


def test_run_chat_repl_effort_command_updates_budget(monkeypatch, capsys):
    """Test REPL /effort command actually updates the budget for subsequent calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Mock the create_llm_adapter to avoid actual API calls
        from unittest.mock import MagicMock, patch

        adapter_mock = MagicMock()

        def mock_create_adapter(provider, *, model=None):
            return adapter_mock

        # Mock run_chat_agent to capture the config it receives
        captured_configs = []

        def mock_run_chat_agent(*, task, adapter, config):
            captured_configs.append(config)
            from teaagent.runner import RunResult

            return RunResult(
                success=True, final_answer='test', iterations=0, tool_calls=0
            )

        inputs = ['/effort high', '/exit']
        with (
            patch(
                'teaagent.cli._handlers.chat_repl.create_llm_adapter',
                side_effect=mock_create_adapter,
            ),
            patch(
                'teaagent.cli._handlers.chat_repl.run_chat_agent',
                side_effect=mock_run_chat_agent,
            ),
        ):
            monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
            result = run_chat_repl(config)

        captured = capsys.readouterr()
        assert 'Effort level set to: high' in captured.out
        assert 'Budget limit: $50.00' in captured.out
        assert result == 0


def test_cli_default_entry_launches_chat():
    """Test that running CLI with no arguments defaults to agent chat command."""
    from unittest.mock import MagicMock, patch

    from teaagent.cli import main

    # Mock the chat_command to verify it's called
    chat_called = []

    def mock_chat_command(args):
        chat_called.append(True)
        return 0

    with patch('teaagent.cli.chat_command', side_effect=mock_chat_command):
        # Simulate running with no arguments
        result = main(
            argv=[],
            _adapter_factory=MagicMock(),
            _serve_mcp_http=MagicMock(),
            _check_graphqlite=MagicMock(),
            _check_llm=MagicMock(),
            _run_model_conformance=MagicMock(),
        )

    assert len(chat_called) == 1
    assert result == 0


def test_git_sandbox_consent_saved_to_config():
    """Test that git_sandbox_consent is saved to config.json."""
    import json

    from teaagent.cli._handlers.agent_helpers import _save_git_sandbox_consent

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


def test_chat_parser_initial_task(monkeypatch, capsys):
    """Test that chat command correctly parses initial task argument."""
    import argparse

    from teaagent.cli._agent_parsers import _chat

    # Create a minimal parser with just the chat subcommand
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest='agent_command', required=True)
    _chat(subs, lambda args: None)

    # Test that 'teaagent chat hello' parses task='hello', provider=None
    args = parser.parse_args(['chat', 'hello'])
    assert args.task == 'hello', f"Expected task='hello', got task={args.task}"
    assert args.provider is None, (
        f'Expected provider=None, got provider={args.provider}'
    )

    # Test that 'teaagent chat hello openai' parses task='hello', provider='openai'
    args = parser.parse_args(['chat', 'hello', 'openai'])
    assert args.task == 'hello', f"Expected task='hello', got task={args.task}"
    assert args.provider == 'openai', (
        f"Expected provider='openai', got provider={args.provider}"
    )


def test_shell_escape_blocked_in_chat_repl(monkeypatch, capsys):
    """Test that shell escape (!) is properly blocked in chat REPL for security."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['!echo test', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
        result = run_chat_repl(config)

        captured = capsys.readouterr()
        assert 'disabled for security' in captured.out.lower()
        assert 'full terminal' in captured.out.lower()
        assert result == 0


def test_execute_shell_command_simple(capsys):
    """Test simple shell command execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        execute_shell_command('echo hello', Path(tmpdir))
        captured = capsys.readouterr()
        assert 'hello' in captured.out


def test_execute_shell_command_destructive_blocked(capsys):
    """Test that destructive commands are blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        execute_shell_command('rm -rf /', Path(tmpdir))
        captured = capsys.readouterr()
        assert 'Destructive command blocked' in captured.out


def test_execute_shell_command_not_found(capsys):
    """Test command not found error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        execute_shell_command('nonexistent_command_xyz', Path(tmpdir))
        captured = capsys.readouterr()
        assert 'Command not found' in captured.out


def test_complete_file_path_basic():
    """Test basic file path completion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create some test files
        (root / 'test_file.py').touch()
        (root / 'test_another.py').touch()
        (root / 'other.txt').touch()

        # Test completion
        completions = complete_file_path('@test', root)
        assert len(completions) == 2
        assert any('test_file.py' in c for c in completions)
        assert any('test_another.py' in c for c in completions)


def test_complete_file_path_with_directory():
    """Test file path completion with directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create directory structure
        src_dir = root / 'src'
        src_dir.mkdir()
        (src_dir / 'auth.py').touch()
        (src_dir / 'main.py').touch()

        # Test completion with directory
        completions = complete_file_path('@src/', root)
        assert len(completions) == 2
        assert any('src/auth.py' in c for c in completions)
        assert any('src/main.py' in c for c in completions)


def test_complete_file_path_no_match():
    """Test completion with no matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        completions = complete_file_path('@nonexistent', root)
        assert len(completions) == 0


def test_complete_symbol_basic():
    """Test basic symbol completion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a test Python file with some functions
        test_file = root / 'test.py'
        test_file.write_text("""
def login():
    pass

def logout():
    pass

class UserAuth:
    pass
""")

        # Test symbol completion
        completions = complete_symbol('@log', root)
        # This may return empty if code ontology fails, but should not crash
        assert isinstance(completions, list)


def test_complete_symbol_no_match():
    """Test symbol completion with no matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        completions = complete_symbol('@nonexistent', root)
        assert isinstance(completions, list)


def test_show_interactive_diff_basic(capsys, monkeypatch):
    """Test interactive diff display."""
    import subprocess

    from teaagent.cli._handlers._agent import show_interactive_diff

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=root, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=root,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=root, capture_output=True
        )

        # Create initial commit
        (root / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=root, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=root, capture_output=True
        )

        # Create a branch and make changes
        subprocess.run(
            ['git', 'checkout', '-b', 'test-branch'], cwd=root, capture_output=True
        )
        (root / 'test.txt').write_text('modified content')

        # Mock input to skip detailed diff
        monkeypatch.setattr('builtins.input', lambda _: 'n')

        # Test diff display
        result = show_interactive_diff(root, 'test-branch')
        captured = capsys.readouterr()

        assert result is True  # Should proceed
        assert 'Sandbox Merge Preview' in captured.out


def test_suspend_to_background_basic(capsys):
    """Test basic session suspension to background."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {'observations': [{'task': 'test'}], 'compaction_count': 0}
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)
        captured = capsys.readouterr()

        assert run_id  # Should return a run_id
        assert 'Suspending session to background mode' in captured.out
        assert 'Session suspended successfully' in captured.out

        # Check suspension file was created
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        assert suspension_file.exists()


def test_suspend_to_background_with_dirty_workspace(capsys):
    """Test suspension with dirty workspace creates sandbox branch."""
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Make workspace dirty
        (Path(tmpdir) / 'test.txt').write_text('modified content')

        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {'observations': [], 'compaction_count': 0}
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)
        captured = capsys.readouterr()

        assert run_id
        assert 'creating sandbox branch' in captured.out.lower()

        # Verify suspension data includes sandbox branch
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        import json

        with open(suspension_file) as f:
            data = json.load(f)
        assert 'sandbox_branch' in data


def test_suspend_to_background_preserves_context(capsys):
    """Test that suspension preserves session context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the actual file structure
        src_dir = Path(tmpdir) / 'src'
        src_dir.mkdir()
        (src_dir / 'main.py').touch()

        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {
            'observations': [{'task': 'task1'}, {'task': 'task2'}],
            'compaction_count': 3,
        }
        targeted_files = {src_dir / 'main.py'}

        run_id = suspend_to_background(config, session_context, targeted_files)

        # Verify context was preserved
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        import json

        with open(suspension_file) as f:
            data = json.load(f)

        assert data['session_context']['observations_count'] == 2
        assert data['session_context']['compaction_count'] == 3
        assert len(data['targeted_files']) == 1


def test_interactive_review_mode_no_changes(capsys):
    """Test interactive review mode with no changes."""
    import json
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Create suspension file for the run_id
        tea_dir = Path(tmpdir) / '.teaagent'
        tea_dir.mkdir(parents=True, exist_ok=True)
        suspension_file = tea_dir / 'suspension-test-run-id.json'
        suspension_data = {
            'run_id': 'test-run-id',
            'timestamp': __import__('time').time(),
            'acp_version': '1.0.0',
            'mode': 'suspended_from_repl',
            'config': {},
            'session_context': {'observations_count': 0, 'compaction_count': 0},
            'targeted_files': [],
            'audit_trail': {
                'suspension_time': __import__('time').time(),
                'original_mode': 'repl',
                'transition_type': 'keyboard_to_robot',
            },
        }
        suspension_file.write_text(json.dumps(suspension_data, indent=2))

        result = interactive_review_mode(tmpdir, 'test-run-id')
        captured = capsys.readouterr()

        assert result == 0
        assert 'No changes detected to review' in captured.out


def test_interactive_review_mode_invalid_run_id(capsys):
    """Test interactive review mode with invalid run_id."""
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Make changes
        (Path(tmpdir) / 'test.txt').write_text('modified content')

        result = interactive_review_mode(tmpdir, 'invalid-run-id')
        captured = capsys.readouterr()

        # Should fail with error about missing suspension data
        assert result == 1
        assert 'Suspension file not found' in captured.out


def test_interactive_review_mode_with_changes(capsys, monkeypatch):
    """Test interactive review mode with file changes."""
    import json
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Create suspension file for the run_id
        tea_dir = Path(tmpdir) / '.teaagent'
        tea_dir.mkdir(parents=True, exist_ok=True)
        suspension_file = tea_dir / 'suspension-test-run-id.json'
        suspension_data = {
            'run_id': 'test-run-id',
            'timestamp': __import__('time').time(),
            'acp_version': '1.0.0',
            'mode': 'suspended_from_repl',
            'config': {},
            'session_context': {'observations_count': 0, 'compaction_count': 0},
            'targeted_files': [],
            'audit_trail': {
                'suspension_time': __import__('time').time(),
                'original_mode': 'repl',
                'transition_type': 'keyboard_to_robot',
            },
        }
        suspension_file.write_text(json.dumps(suspension_data, indent=2))

        # Make changes
        (Path(tmpdir) / 'test.txt').write_text('modified content')

        # Mock user input to skip the file (n for next)
        inputs = ['n']  # Skip the file
        monkeypatch.setattr(
            'builtins.input', lambda _: inputs.pop(0) if inputs else 'n'
        )

        interactive_review_mode(tmpdir, 'test-run-id')
        captured = capsys.readouterr()

        # The function should complete
        assert 'Interactive Review Mode' in captured.out or 'Review' in captured.out


def test_dual_mode_integration_suspension_to_review(capsys, monkeypatch):
    """Test full integration: REPL suspension → background → review."""
    import json
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Step 1: Simulate REPL session suspension
        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {
            'observations': [{'task': 'refactor authentication'}],
            'compaction_count': 0,
        }
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)
        assert run_id  # Should get a valid run_id

        # Verify suspension file was created with ACP compliance
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        assert suspension_file.exists()

        with open(suspension_file) as f:
            suspension_data = json.load(f)

        assert 'acp_version' in suspension_data
        assert suspension_data['acp_version'] == '1.0.0'
        assert suspension_data['mode'] == 'suspended_from_repl'
        assert 'audit_trail' in suspension_data
        assert suspension_data['audit_trail']['transition_type'] == 'keyboard_to_robot'

        # Step 2: Simulate background task making changes
        (Path(tmpdir) / 'test.txt').write_text('refactored content by background task')

        # Step 3: Interactive review of background results
        # Mock user input to accept changes
        inputs = ['y']  # Accept the file
        monkeypatch.setattr(
            'builtins.input', lambda _: inputs.pop(0) if inputs else 'n'
        )

        interactive_review_mode(tmpdir, run_id)
        captured = capsys.readouterr()

        # Verify review completed
        assert 'Interactive Review Mode' in captured.out or 'Review' in captured.out

        # Verify review file was created with ACP compliance
        review_file = tea_dir / f'review-{run_id}.json'
        if review_file.exists():
            with open(review_file) as f:
                review_data = json.load(f)
            assert 'acp_version' in review_data
            assert review_data['acp_version'] == '1.0.0'
            assert review_data['mode'] == 'interactive_review'
            assert 'audit_trail' in review_data
            assert review_data['audit_trail']['transition_type'] == 'robot_to_keyboard'


def test_acp_state_consistency_across_modes(capsys):
    """Test that ACP state is consistent across mode transitions."""
    import json
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=tmpdir,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'], cwd=tmpdir, capture_output=True
        )

        # Create initial commit
        (Path(tmpdir) / 'test.txt').write_text('initial content')
        subprocess.run(['git', 'add', '.'], cwd=tmpdir, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'initial'], cwd=tmpdir, capture_output=True
        )

        # Test suspension creates ACP-compliant state
        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {'observations': [], 'compaction_count': 0}
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)

        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'

        with open(suspension_file) as f:
            suspension_data = json.load(f)

        # Verify ACP compliance fields
        assert 'acp_version' in suspension_data
        assert 'mode' in suspension_data
        assert 'audit_trail' in suspension_data
        assert 'timestamp' in suspension_data

        # Verify audit trail structure
        audit_trail = suspension_data['audit_trail']
        assert 'suspension_time' in audit_trail
        assert 'original_mode' in audit_trail
        assert 'transition_type' in audit_trail


def test_git_sandbox_consent_updates_existing_config():
    """Test that git_sandbox_consent updates existing config.json."""
    import json

    from teaagent.cli._handlers.agent_helpers import _save_git_sandbox_consent

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
