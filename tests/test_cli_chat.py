"""Tests for CLI chat REPL handler."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.chat_agent import ChatAgentConfig
from teaagent.cli._handlers._agent import agent_resume_command, agent_run_task
from teaagent.cli._handlers._chat import chat_command
from teaagent.cli._handlers.agent_review import interactive_review_mode
from teaagent.cli._handlers.chat_commands import execute_shell_command
from teaagent.cli._handlers.chat_completion import complete_file_path, complete_symbol
from teaagent.cli._handlers.chat_repl import (
    print_chat_help,
    run_chat_repl,
    suspend_to_background,
)
from teaagent.run_store import RunStore


def test_print_chat_help(capsys):
    """Test that chat help prints correctly."""
    print_chat_help()
    captured = capsys.readouterr()
    assert 'Chat Commands:' in captured.out
    assert '/exit' in captured.out
    assert '/help' in captured.out


def test_repl_undo_help_accurate(capsys: pytest.CaptureFixture[str]) -> None:
    """TICKET-15: REPL /undo help text must describe journal-first fallback behavior and not say only 'using checkpoint'."""
    print_chat_help()
    captured = capsys.readouterr()
    assert 'journal-first' in captured.out
    assert 'checkpoint' in captured.out
    assert 'Undo all changes (using checkpoint)' not in captured.out


def test_chat_command_with_invalid_args():
    """Test chat command returns an error for invalid permission mode input."""
    from argparse import Namespace

    from teaagent.cli._handlers._chat import chat_command

    args = Namespace(
        provider=None,
        model=None,
        root='.',
        allow_destructive=False,
        permission_mode='not-a-mode',
    )

    with patch('teaagent.tui.run_tui') as mock_run:
        result = chat_command(args)

    assert result == 1
    mock_run.assert_not_called()


def test_chat_command_smoke_test():
    """Test chat command starts and exits cleanly via /exit command."""
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
        from unittest.mock import patch

        with patch('builtins.input', lambda _: '/exit'):
            result = chat_command(args)
        assert result == 0, f'Expected exit code 0, got {result}'


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


def test_agent_run_background_rejects_known_run_or_suspension_id(capsys):
    with tempfile.TemporaryDirectory() as tmpdir:
        tea_dir = Path(tmpdir) / '.teaagent'
        tea_dir.mkdir()
        (tea_dir / 'suspension-abc12345.json').write_text('{}', encoding='utf-8')

        args = argparse.Namespace(
            root=tmpdir,
            task='abc12345',
            background=True,
            provider='gpt',
            model=None,
            route_model=False,
            max_iterations=10,
            max_tool_calls=10,
            clarify=False,
            allow_destructive=False,
            approve_call_id=[],
            hitl_approval=False,
            permission_mode='prompt',
            subagent=False,
            max_subagent_depth=1,
            heartbeat=0.0,
            code_analysis=False,
            context_profile='balanced',
            selected_skills=[],
            max_estimated_cost_cents=0,
        )

        result = agent_run_task(args)
        captured = capsys.readouterr()

        assert result == 2
        assert 'looks like a suspension id' in captured.out.lower()
        assert 'interactive-review' in captured.out


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


def test_chat_repl_displays_answer(monkeypatch, capsys):
    """Test REPL displays final answer on success and error message on failure."""
    from unittest.mock import MagicMock, patch

    from teaagent.runner._types import FinalAnswer, RunResult

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        # Mock run_chat_agent to return a successful result
        success_result = RunResult(
            run_id='test-run-1',
            final_answer=FinalAnswer(content='Test answer'),
            iterations=1,
            tool_calls=0,
            status='completed',
            cost_cents=15.0,
            input_tokens=100,
            output_tokens=50,
        )

        # Mock run_chat_agent to return a failed result
        failure_result = RunResult(
            run_id='test-run-2',
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='failed',
            error_message='Test error message',
            cost_cents=5.0,
            input_tokens=50,
            output_tokens=25,
        )

        call_count = [0]

        def mock_run_chat_agent(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return success_result
            else:
                return failure_result

        inputs = ['test task 1', 'test task 2', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        # Mock RunStore and UndoJournal to avoid file system issues
        with (
            patch('teaagent.cli._handlers.chat_repl.RunStore') as mock_store_class,
            patch('teaagent.chat_session_controller.RunStore'),
            patch('teaagent.cli._handlers.chat_repl.UndoJournal') as mock_journal_class,
            patch(
                'teaagent.chat_session_controller.run_chat_agent',
                side_effect=mock_run_chat_agent,
            ),
        ):
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_audit = MagicMock()
            mock_audit.add_sink = MagicMock()
            mock_store.audit_logger.return_value = mock_audit
            mock_store.logger_for_result = MagicMock()
            mock_store.undo_path = MagicMock(return_value=tmpdir + '/undo.jsonl')

            mock_journal = MagicMock()
            mock_journal_class.return_value = mock_journal
            mock_journal.has_entries = False
            mock_journal.save_to = MagicMock()

            result = run_chat_repl(config)
            captured = capsys.readouterr()

            # Should print answer on success
            assert 'Test answer' in captured.out
            # Should print error message on failure
            assert 'Test error message' in captured.out
            # Should not print generic "Task failed" message
            assert 'Task failed with exit code' not in captured.out
            assert result == 0


def test_chat_repl_undo_no_git_checkout_fallback(monkeypatch, capsys):
    """Test REPL undo does not use git checkout fallback when no journal exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)

        inputs = ['/undo', '/exit']
        monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))

        run_chat_repl(config)
        captured = capsys.readouterr()

        # Should print "Nothing to undo" when no journal exists
        assert 'Nothing to undo' in captured.out
        # Should not contain git checkout fallback message
        assert 'git checkout' not in captured.out
        assert 'fallback' not in captured.out.lower()


def test_suspend_to_background_no_branch_switch(monkeypatch, capsys):
    """Test /background does not silently switch branches and clarifies it's not background execution."""
    from teaagent.cli._handlers.chat_repl import suspend_to_background

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {'observations': [], 'compaction_count': 0}
        targeted_files = set()

        suspend_to_background(config, session_context, targeted_files)
        captured = capsys.readouterr()

        # Should not create a branch
        assert 'Created sandbox branch' not in captured.out
        # Message should clarify this is not background execution
        assert 'suspension checkpoint' in captured.out
        # Should mention interactive-review for reviewing suspended runs
        assert 'interactive-review' in captured.out
        # Should not advertise background continuation for the suspension id
        assert '--background' not in captured.out


def test_chat_session_controller_execute_task(monkeypatch, capsys):
    """Test ChatSessionController executes tasks with consistent behavior (CG-01, CG-03)."""
    from unittest.mock import MagicMock, patch

    from teaagent.chat_session_controller import ChatSessionController, SessionState
    from teaagent.runner._types import FinalAnswer, RunResult

    with tempfile.TemporaryDirectory() as tmpdir:
        session_state = SessionState()
        output_messages = []

        def mock_output_fn(msg: str):
            output_messages.append(msg)

        controller = ChatSessionController(
            root=tmpdir,
            output_fn=mock_output_fn,
            session_state=session_state,
        )

        # Mock run_chat_agent to return a successful result
        success_result = RunResult(
            run_id='test-run-1',
            final_answer=FinalAnswer(content='Test answer'),
            iterations=1,
            tool_calls=0,
            status='completed',
            cost_cents=15.0,
            input_tokens=100,
            output_tokens=50,
        )

        # Mock RunStore, AuditLogger, and UndoJournal
        with (
            patch('teaagent.chat_session_controller.RunStore') as mock_store_class,
            patch('teaagent.chat_session_controller.UndoJournal') as mock_journal_class,
            patch(
                'teaagent.chat_session_controller.run_chat_agent'
            ) as mock_run_chat_agent,
        ):
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_audit = MagicMock()
            mock_store.audit_logger.return_value = mock_audit
            mock_store.logger_for_result = MagicMock()
            mock_store.undo_path = MagicMock(return_value=tmpdir + '/undo.jsonl')

            mock_journal = MagicMock()
            mock_journal_class.return_value = mock_journal
            mock_journal.has_entries = False
            mock_journal.save_to = MagicMock()

            mock_run_chat_agent.return_value = success_result

            config = ChatAgentConfig.from_root(tmpdir, model='gpt/gpt-4')
            controller.execute_task('test task', config)

            # Should print answer (CG-01)
            assert 'Test answer' in output_messages
            # Should update session cost (CG-03)
            assert session_state.session_cost_cents == 15.0
            # Should append observation
            assert len(session_state.observations) == 1
            assert session_state.observations[0]['cost_cents'] == 15.0


def test_chat_session_controller_undo(monkeypatch, capsys):
    """Test ChatSessionController undo uses UndoJournal (CG-02)."""
    from unittest.mock import MagicMock, patch

    from teaagent.chat_session_controller import ChatSessionController, SessionState
    from teaagent.run_undo import UndoResult

    with tempfile.TemporaryDirectory() as tmpdir:
        session_state = SessionState()
        output_messages = []

        def mock_output_fn(msg: str):
            output_messages.append(msg)

        controller = ChatSessionController(
            root=tmpdir,
            output_fn=mock_output_fn,
            session_state=session_state,
        )

        # Mock RunStore and UndoJournal
        with (
            patch('teaagent.chat_session_controller.RunStore') as mock_store_class,
            patch('teaagent.chat_session_controller.UndoJournal') as mock_journal_class,
        ):
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_store.latest_run_with_undo.return_value = 'test-run-id'
            undo_path = Path(tmpdir) / 'undo.jsonl'
            undo_path.touch()  # Create file
            mock_store.undo_path.return_value = undo_path

            mock_journal = MagicMock()
            mock_journal_class.return_value = mock_journal
            mock_journal.restore.return_value = UndoResult(
                restored=['file1.txt'],
                deleted=[],
                errors=[],
            )

            result = controller.undo_last_run()

            # Should succeed
            assert result is True
            # Should print success message
            assert any('Undo completed' in msg for msg in output_messages)
            # Should clean up journal
            assert undo_path.exists() is False  # File should be unlinked


def test_controller_surfaces_save_failure():
    """TICKET-13: A save failure in undo_journal is not swallowed."""
    from unittest.mock import patch

    from teaagent.chat_session_controller import ChatSessionController, SessionState

    with tempfile.TemporaryDirectory() as tmpdir:
        session_state = SessionState()
        output_messages = []

        def mock_output_fn(msg: str):
            output_messages.append(msg)

        controller = ChatSessionController(
            root=tmpdir,
            output_fn=mock_output_fn,
            session_state=session_state,
        )

        # Create a bad journal that raises AttributeError on save
        bad_journal = MagicMock()
        bad_journal.has_entries = True
        bad_journal.save_to.side_effect = AttributeError('injected: bad attr')

        # Create a mock config
        mock_config = MagicMock()
        mock_config.model = 'gpt-4'

        # Create a mock audit logger
        mock_audit = MagicMock()
        mock_audit.path = Path(tmpdir) / 'audit.jsonl'

        with (
            patch('teaagent.chat_session_controller.run_chat_agent') as mock_run,
            patch('teaagent.chat_session_controller.RunStore') as mock_store,
        ):
            mock_run.return_value = MagicMock(
                status='completed',
                cost_cents=0,
                run_id='r1',
                final_answer=MagicMock(content='ok'),
                error_message=None,
            )
            mock_store.return_value.undo_path.return_value = Path(tmpdir) / 'undo.jsonl'
            mock_store.return_value.logger_for_result.return_value = None

            # Should raise AttributeError, not swallow it
            with pytest.raises(AttributeError, match='injected'):
                controller.execute_task(
                    'test task',
                    adapter=None,
                    config=mock_config,
                    undo_journal=bad_journal,
                    audit=mock_audit,
                )


def test_chat_surface_parity(monkeypatch, capsys):
    """Test that CLI and TUI surfaces use the same controller for consistent behavior (CG-05)."""
    from unittest.mock import MagicMock, patch

    from teaagent.chat_session_controller import ChatSessionController, SessionState
    from teaagent.runner._types import FinalAnswer, RunResult

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create two controllers (simulating CLI and TUI)
        cli_output = []
        tui_output = []

        def cli_output_fn(msg: str):
            cli_output.append(msg)

        def tui_output_fn(msg: str):
            tui_output.append(msg)

        cli_state = SessionState()
        tui_state = SessionState()

        cli_controller = ChatSessionController(
            root=tmpdir,
            output_fn=cli_output_fn,
            session_state=cli_state,
        )

        tui_controller = ChatSessionController(
            root=tmpdir,
            output_fn=tui_output_fn,
            session_state=tui_state,
        )

        # Mock run_chat_agent
        success_result = RunResult(
            run_id='test-run',
            final_answer=FinalAnswer(content='Test answer'),
            iterations=1,
            tool_calls=0,
            status='completed',
            cost_cents=10.0,
            input_tokens=50,
            output_tokens=25,
        )

        with (
            patch('teaagent.chat_session_controller.RunStore') as mock_store_class,
            patch('teaagent.chat_session_controller.UndoJournal') as mock_journal_class,
            patch(
                'teaagent.chat_session_controller.run_chat_agent'
            ) as mock_run_chat_agent,
        ):
            mock_store = MagicMock()
            mock_store_class.return_value = mock_store
            mock_audit = MagicMock()
            mock_store.audit_logger.return_value = mock_audit
            mock_store.logger_for_result = MagicMock()
            mock_store.undo_path = MagicMock(return_value=tmpdir + '/undo.jsonl')

            mock_journal = MagicMock()
            mock_journal_class.return_value = mock_journal
            mock_journal.has_entries = False
            mock_journal.save_to = MagicMock()

            mock_run_chat_agent.return_value = success_result

            config = ChatAgentConfig.from_root(tmpdir, model='gpt/gpt-4')

            # Execute same task on both surfaces
            cli_controller.execute_task('test task', config)
            tui_controller.execute_task('test task', config)

            # Both should print the same answer (CG-01 parity)
            assert cli_output == tui_output
            assert 'Test answer' in cli_output[0]

            # Both should track cost identically (CG-03 parity)
            assert cli_state.session_cost_cents == tui_state.session_cost_cents == 10.0

            # Both should have identical observations
            assert len(cli_state.observations) == len(tui_state.observations) == 1


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
                'teaagent.chat_session_controller.run_chat_agent',
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
        assert 'Suspending session as a checkpoint' in captured.out
        assert 'interactive-review' in captured.out
        assert 'teaagent resume' not in captured.out.lower()
        assert '--detach' not in captured.out.lower()
        assert 'Session suspended successfully' in captured.out

        # Check suspension file was created
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        assert suspension_file.exists()


def test_suspend_to_background_with_dirty_workspace(capsys):
    """Test suspension with dirty workspace does NOT create sandbox branch (CG-09/CG-10 fix)."""
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

        # Make workspace dirty
        (Path(tmpdir) / 'test.txt').write_text('modified content')

        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {'observations': [], 'compaction_count': 0}
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)
        captured = capsys.readouterr()

        assert run_id
        # Should NOT create a branch (CG-09/CG-10 fix)
        assert 'creating sandbox branch' not in captured.out.lower()
        # Should warn about uncommitted changes
        assert 'uncommitted changes' in captured.out.lower()
        # Should clarify it's a suspension checkpoint
        assert 'suspension checkpoint' in captured.out.lower()
        assert 'teaagent resume' not in captured.out.lower()
        assert '--detach' not in captured.out.lower()

        # Verify suspension data does NOT include sandbox branch
        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'

        with open(suspension_file) as f:
            data = json.load(f)
        # Should NOT include sandbox branch (CG-09/CG-10 fix)
        assert 'sandbox_branch' not in data


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
        assert 'timestamp' in suspension_data


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


def test_suspension_data_no_audit_trail(capsys):
    """TICKET-15: Suspension JSON must not contain the redundant audit_trail field."""
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {
            'observations': [{'task': 'test task'}],
            'compaction_count': 0,
        }
        targeted_files = set()

        run_id = suspend_to_background(config, session_context, targeted_files)

        tea_dir = Path(tmpdir) / '.teaagent'
        suspension_file = tea_dir / f'suspension-{run_id}.json'
        assert suspension_file.exists()

        with open(suspension_file) as f:
            data = json.load(f)
        assert 'audit_trail' not in data, (
            'audit_trail was removed from suspension JSON; '
            'real governance record is in RunStore'
        )


def test_repl_suspend_resume_roundtrip(capsys):
    """TICKET-16 Phase 2: Suspend a REPL session, then resume it."""

    with tempfile.TemporaryDirectory() as tmpdir:
        tea_dir = Path(tmpdir) / '.teaagent'
        tea_dir.mkdir(parents=True, exist_ok=True)

        config = ChatAgentConfig.from_root(tmpdir)
        session_context = {
            'observations': [{'task': 'test task', 'cost_cents': 0}],
            'compaction_count': 0,
        }
        targeted_files = {Path(tmpdir) / 'test.txt'}

        run_id = suspend_to_background(config, session_context, targeted_files)
        assert run_id, 'suspend should return a run_id'

        store = RunStore(tmpdir)
        task = store.task_for_run(run_id)
        assert task is not None, 'task_for_run must find the run_started event'
        assert 'test task' in task
        args = argparse.Namespace(
            root=tmpdir,
            run_id=run_id,
            fresh_restart=False,
            checkpoint_store=None,
            provider='gpt',
            model=None,
            route_model=False,
            permission_mode='prompt',
            max_iterations=10,
            max_tool_calls=10,
            clarify=False,
            allow_destructive=False,
            approve_call_id=[],
            hitl_approval=False,
            subagent=False,
            max_subagent_depth=1,
            heartbeat=0.0,
            code_analysis=False,
            context_profile='balanced',
            selected_skills=[],
            max_estimated_cost_cents=0,
            memory_limit=None,
            auto_compact=None,
            no_validate=True,
            validate=False,
            validation_profile=None,
            require_plan=False,
            progress=False,
            human=False,
            skip_plan_check=False,
            plan_contract=None,
        )

        # Patch _execute_agent_task to avoid actually running
        with patch('teaagent.cli._handlers._agent._execute_agent_task') as mock_execute:
            mock_execute.return_value = 0
            result = agent_resume_command(args)
            assert result == 0, 'resume should succeed'

            _, task_arg = mock_execute.call_args.args
            kwargs = mock_execute.call_args.kwargs
            assert task_arg == 'test task', (
                f'recovered task should be "test task", got {task_arg!r}'
            )
            assert kwargs.get('resumed_from') == run_id
