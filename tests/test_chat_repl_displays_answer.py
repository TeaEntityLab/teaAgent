"""AC: REPL displays answers and reports status correctly (P0-1, fixes CG-01)."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import FakeAdapter

from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_session_controller import ChatSessionController
from teaagent.cli._handlers._chat import chat_command
from teaagent.runner import RunResult


def test_controller_displays_answer_on_success(tmp_path: Path) -> None:
    """Test that successful task displays final_answer content (CG-01)."""
    outputs = [
        '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"test.txt","content":"hello"},"call_id":"1"}',
        '{"type":"final","content":"Task completed successfully"}',
    ]
    adapter = FakeAdapter(outputs)

    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    config = ChatAgentConfig.from_root(tmp_path)
    # Use allow permission mode to auto-approve tool calls for test
    config = ChatAgentConfig(
        root=tmp_path,
        model='gpt/gpt-4',
        permission_mode='allow',
        max_iterations=10,
        max_tool_calls=10,
        max_estimated_cost_cents=1000,
    )
    result = controller.execute_task(
        task='write a file',
        config=config,
        adapter=adapter,
    )

    output = output_buffer.getvalue()
    assert 'Task completed successfully' in output, (
        f'Expected answer in output, got: {output}'
    )
    assert 'Task failed' not in output, 'Should not print "Task failed" on success'
    assert result.run_result.status == 'completed'


def test_controller_displays_error_on_failure(tmp_path: Path) -> None:
    """Test that failed task prints error message, not RunResult repr (CG-01)."""
    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    config = ChatAgentConfig.from_root(tmp_path)
    with patch('teaagent.chat_session_controller.run_chat_agent') as mock_run:
        mock_run.return_value = RunResult(
            run_id='test-run',
            status='failed',
            final_answer=None,
            error_message='permission denied',
            cost_cents=0,
            input_tokens=0,
            output_tokens=0,
            iterations=1,
            tool_calls=0,
        )

        # Mock audit to avoid file operations
        mock_audit = MagicMock()
        mock_audit.path = None  # This triggers the skip path in execute_task

        result = controller.execute_task(
            task='fail task',
            config=config,
            audit=mock_audit,
        )

    output = output_buffer.getvalue()
    assert 'permission denied' in output or '[failed]' in output, (
        f'Expected error message, got: {output}'
    )
    assert 'RunResult' not in output, f'Should not print RunResult repr, got: {output}'
    assert result.run_result.status == 'failed'


def test_controller_no_output_on_empty_final_answer(tmp_path: Path) -> None:
    """Test that task with no final_answer prints status, not crash (CG-01)."""
    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    config = ChatAgentConfig.from_root(tmp_path)
    with patch('teaagent.chat_session_controller.run_chat_agent') as mock_run:
        mock_run.return_value = RunResult(
            run_id='test-run',
            status='completed',
            final_answer=None,
            error_message=None,
            cost_cents=0,
            input_tokens=0,
            output_tokens=0,
            iterations=1,
            tool_calls=0,
        )

        # Mock audit to avoid file operations
        mock_audit = MagicMock()
        mock_audit.path = None  # This triggers the skip path in execute_task

        result = controller.execute_task(
            task='empty task',
            config=config,
            audit=mock_audit,
        )

    output = output_buffer.getvalue()
    # Should print status but not crash
    assert '[completed]' in output or output == '', f'Unexpected output: {output}'
    assert result.run_result.status == 'completed'


# ── TASK-DD2-001: Execute or reject `teaagent chat <task>` ─────────────────────


def test_chat_command_executes_initial_task(tmp_path: Path) -> None:
    """Test that chat_command with args.task executes the task before REPL loop."""
    from argparse import Namespace

    # Create mock args with task
    args = Namespace(
        task='do something',
        provider=None,
        model=None,
        root=str(tmp_path),
        allow_destructive=False,
        permission_mode='prompt',
        max_iterations=10,
        max_tool_calls=10,
        max_estimated_cost_cents=0,
        subagent=False,
        max_subagent_depth=1,
        heartbeat=0.0,
        stream=False,
        enable_git_tools=False,
        skill_search_dirs=None,
        memory_limit=5,
    )

    # Mock run_tui to capture the initial_task parameter
    # run_tui is imported inside chat_command, so we patch it at the tui module
    with patch('teaagent.tui.run_tui') as mock_run_tui:
        mock_run_tui.return_value = 0

        result = chat_command(args)

        # Verify run_tui was called with initial_task
        mock_run_tui.assert_called_once()
        call_kwargs = mock_run_tui.call_args[1]
        assert call_kwargs['initial_task'] == 'do something'
        assert result == 0


def test_chat_command_no_task_opens_repl(tmp_path: Path) -> None:
    """Test that chat_command with args.task=None opens REPL without executing task."""
    from argparse import Namespace

    # Create mock args without task
    args = Namespace(
        task=None,
        provider=None,
        model=None,
        root=str(tmp_path),
        allow_destructive=False,
        permission_mode='prompt',
        max_iterations=10,
        max_tool_calls=10,
        max_estimated_cost_cents=0,
        subagent=False,
        max_subagent_depth=1,
        heartbeat=0.0,
        stream=False,
        enable_git_tools=False,
        skill_search_dirs=None,
        memory_limit=5,
    )

    # Mock run_tui to capture the initial_task parameter
    with patch('teaagent.tui.run_tui') as mock_run_tui:
        mock_run_tui.return_value = 0

        result = chat_command(args)

        # Verify run_tui was called with initial_task=None
        mock_run_tui.assert_called_once()
        call_kwargs = mock_run_tui.call_args[1]
        assert call_kwargs['initial_task'] is None
        assert result == 0
