"""AC: REPL displays answers and reports status correctly (P0-1, fixes CG-01)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import FakeAdapter
from teaagent.chat_agent import ChatAgentConfig
from teaagent.chat_session_controller import ChatSessionController
from teaagent.runner import RunResult


def test_controller_displays_answer_on_success(tmp_path: Path) -> None:
    """Test that successful task displays final_answer content (CG-01)."""
    outputs = [
        '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"test.txt","content":"hello"},"call_id":"1"}',
        '{"type":"final","content":"Task completed successfully"}',
    ]
    adapter = FakeAdapter(outputs)

    output_buffer = io.StringIO()
    output_fn = lambda s: output_buffer.write(s + '\n')

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
    assert 'Task completed successfully' in output, f'Expected answer in output, got: {output}'
    assert 'Task failed' not in output, f'Should not print "Task failed" on success'
    assert result.run_result.status == 'completed'


def test_controller_displays_error_on_failure(tmp_path: Path) -> None:
    """Test that failed task prints error message, not RunResult repr (CG-01)."""
    output_buffer = io.StringIO()
    output_fn = lambda s: output_buffer.write(s + '\n')

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
    assert 'permission denied' in output or '[failed]' in output, f'Expected error message, got: {output}'
    assert 'RunResult' not in output, f'Should not print RunResult repr, got: {output}'
    assert result.run_result.status == 'failed'


def test_controller_no_output_on_empty_final_answer(tmp_path: Path) -> None:
    """Test that task with no final_answer prints status, not crash (CG-01)."""
    output_buffer = io.StringIO()
    output_fn = lambda s: output_buffer.write(s + '\n')

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
