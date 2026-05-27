"""Tests for unified background runner (ultrawork deprecation)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from teaagent.ergonomics.background_run import BackgroundRunStore


def test_background_run_store_start(tmp_path: Path) -> None:
    """Test starting a background run."""
    store = BackgroundRunStore(tmp_path)
    command = ['echo', 'test']
    record = store.start(command, label='test-label')

    assert record.background_id
    assert record.command == command
    assert record.label == 'test-label'
    assert record.pid > 0
    assert record.log_path
    assert record.started_at


def test_background_run_store_list(tmp_path: Path) -> None:
    """Test listing background runs."""
    store = BackgroundRunStore(tmp_path)
    store.start(['echo', 'test1'], label='label1')
    store.start(['echo', 'test2'], label='label2')

    runs = store.list()
    assert len(runs) == 2
    assert all('background_id' in r for r in runs)
    assert all('pid' in r for r in runs)


def test_background_run_store_get(tmp_path: Path) -> None:
    """Test getting a specific background run."""
    store = BackgroundRunStore(tmp_path)
    record = store.start(['echo', 'test'], label='test-label')

    retrieved = store.get(record.background_id)
    assert retrieved['background_id'] == record.background_id
    assert retrieved['label'] == 'test-label'


def test_background_run_store_get_missing(tmp_path: Path) -> None:
    """Test getting a non-existent background run."""
    store = BackgroundRunStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.get('nonexistent')


def test_background_run_store_readonly(tmp_path: Path) -> None:
    """Test readonly mode prevents directory creation."""
    # Should not create .teaagent directory
    store = BackgroundRunStore(tmp_path, readonly=True)
    assert not (tmp_path / '.teaagent' / 'background').exists()

    # Should raise on start
    with pytest.raises(IOError, match='Cannot start background run'):
        store.start(['echo', 'test'])


def test_ultrawork_deprecation_redirect(tmp_path: Path) -> None:
    """Test ultrawork handlers redirect to BackgroundRunStore."""
    from teaagent.cli._handlers._misc import ultrawork_list_command

    args = argparse.Namespace(root=str(tmp_path))
    result = ultrawork_list_command(args)

    # Should successfully redirect to BackgroundRunStore
    assert result == 0
