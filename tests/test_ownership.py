"""Tests for WorkspaceRegistry with file_lock and PID takeover."""

import os
from unittest.mock import MagicMock, patch

import pytest

from teaagent.mcp_server import WorkspaceLock, WorkspaceRegistry


def test_workspace_lock_serialization():
    """Test WorkspaceLock serialization."""
    lock = WorkspaceLock(
        workspace_path='/test/path', owner_pid=12345, acquired_at='2024-01-01T00:00:00Z'
    )

    data = lock.to_dict()
    restored = WorkspaceLock.from_dict(data)

    assert restored.workspace_path == lock.workspace_path
    assert restored.owner_pid == lock.owner_pid
    assert restored.acquired_at == lock.acquired_at


def test_registry_acquire_lock(tmp_path):
    """Test acquiring a workspace lock."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    lock = registry.acquire_lock('/workspace/test')

    assert lock.workspace_path == '/workspace/test'
    assert lock.owner_pid == os.getpid()


def test_registry_release_lock(tmp_path):
    """Test releasing a workspace lock."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    registry.acquire_lock('/workspace/test')
    registry.release_lock('/workspace/test')

    data = registry._load_registry()
    assert len(data.get('locks', [])) == 0


def test_registry_zombie_cleanup(tmp_path):
    """Test automatic cleanup of zombie process locks."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    with patch('teaagent.mcp_server.is_process_alive', return_value=False):
        registry.acquire_lock('/workspace/test')

    with patch('teaagent.mcp_server.is_process_alive', return_value=False):
        registry.acquire_lock('/workspace/test')

    data = registry._load_registry()
    assert len(data.get('locks', [])) == 1


def test_registry_concurrent_lock(tmp_path):
    """Test that concurrent lock acquisition raises error for same workspace."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    with patch('teaagent.mcp_server.is_process_alive', return_value=True):
        registry.acquire_lock('/workspace/test')

    with (
        patch('teaagent.mcp_server.is_process_alive', return_value=True),
        pytest.raises(RuntimeError) as exc_info,
    ):
        registry.acquire_lock('/workspace/test')

    assert 'is locked by PID' in str(exc_info.value)


def test_registry_multiple_workspaces(tmp_path):
    """Test registry with multiple workspace locks."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    registry.acquire_lock('/workspace/test1')
    registry.acquire_lock('/workspace/test2')

    data = registry._load_registry()
    assert len(data.get('locks', [])) == 2


def test_registry_file_lock_protection(tmp_path):
    """Test that file_lock is used for registry operations."""
    registry_path = tmp_path / 'registry.json'
    registry = WorkspaceRegistry(registry_path)

    with patch('teaagent.mcp_server.file_lock') as mock_lock:
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock()

        registry.acquire_lock('/workspace/test')

        assert mock_lock.called
