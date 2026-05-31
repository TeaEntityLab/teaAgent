"""Tests for CLI execution abstraction layer."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from teaagent.cli.execution import (
    AgentExecutionFactory,
    CommandExecutor,
    DefaultCommandExecutor,
)
from teaagent.policy import PermissionMode
from teaagent.runner import RunResult


def test_agent_execution_factory_creates_components(tmp_path: Path) -> None:
    """Test that AgentExecutionFactory creates all required components."""
    factory = AgentExecutionFactory(tmp_path)

    # Test RunStore creation
    store = factory.create_run_store()
    assert store is not None
    assert store.root == tmp_path

    # Test AuditLogger creation
    audit = factory.create_audit_logger(store)
    assert audit is not None

    # Test GitBranchSandbox creation
    git_sandbox = factory.create_git_sandbox(run_id='test-run')
    assert git_sandbox is not None
    assert git_sandbox._run_id == 'test-run'

    # Test UndoJournal creation
    undo_journal = factory.create_undo_journal()
    assert undo_journal is not None

    # Test ChatAgentConfig creation
    config = factory.create_chat_agent_config(
        max_iterations=5,
        max_tool_calls=10,
        permission_mode=PermissionMode.READ_ONLY,
    )
    assert config is not None
    assert config.max_iterations == 5
    assert config.max_tool_calls == 10
    assert config.permission_mode == PermissionMode.READ_ONLY


def test_agent_execution_factory_creates_execution_context(tmp_path: Path) -> None:
    """Test that AgentExecutionFactory creates ExecutionContext."""
    factory = AgentExecutionFactory(tmp_path)
    store = factory.create_run_store()
    audit = factory.create_audit_logger(store)
    config = factory.create_chat_agent_config()

    mock_adapter = MagicMock()
    context = factory.create_execution_context(
        task='test task',
        adapter=mock_adapter,
        config=config,
        audit=audit,
        store=store,
    )

    assert context is not None
    assert context.task == 'test task'
    assert context.adapter == mock_adapter
    assert context.config == config
    assert context.audit == audit
    assert context.store == store


def test_default_command_executor_is_abstract() -> None:
    """Test that CommandExecutor is abstract and requires execute implementation."""
    with pytest.raises(TypeError):
        CommandExecutor()  # type: ignore[abstract]


def test_default_command_executor_execute(tmp_path: Path) -> None:
    """Test that DefaultCommandExecutor executes correctly."""
    factory = AgentExecutionFactory(tmp_path)
    store = factory.create_run_store()
    audit = factory.create_audit_logger(store)
    config = factory.create_chat_agent_config()

    mock_adapter = MagicMock()
    # Create context without undo_journal to avoid file operations
    context = factory.create_execution_context(
        task='test task',
        adapter=mock_adapter,
        config=config,
        audit=audit,
        store=store,
        undo_journal=None,
    )

    # Mock run_chat_agent to return a fake result
    mock_result = RunResult(
        run_id='test-run-id',
        final_answer=None,
        iterations=1,
        tool_calls=0,
        status='completed',
    )

    with (
        patch('teaagent.cli.execution.run_chat_agent', return_value=mock_result),
        patch.object(context.store, 'logger_for_result'),
    ):
        executor = DefaultCommandExecutor()
        result = executor.execute(context)

    assert result == mock_result
    assert result.run_id == 'test-run-id'


def test_execution_context_dataclass() -> None:
    """Test that ExecutionContext is a proper dataclass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        factory = AgentExecutionFactory(tmp_path)
        store = factory.create_run_store()
        audit = factory.create_audit_logger(store)
        config = factory.create_chat_agent_config()

        mock_adapter = MagicMock()
        context = factory.create_execution_context(
            task='test task',
            adapter=mock_adapter,
            config=config,
            audit=audit,
            store=store,
            task_spec='spec',
            initial_observations=[{'test': 'observation'}],
            initial_context_extra={'extra': 'context'},
        )

        # Verify all fields are set correctly
        assert context.task == 'test task'
        assert context.task_spec == 'spec'
        assert context.initial_observations == [{'test': 'observation'}]
        assert context.initial_context_extra == {'extra': 'context'}
