"""Integration tests for live context anchors features."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.memory.pinned_file import PinnedFile, PinnedFileStorage


class TestPinnedFile:
    """Test PinnedFile data model."""

    def test_create_pinned_file(self) -> None:
        """Test creating a pinned file."""
        pinned = PinnedFile.create('src/test.py')

        assert pinned.file_path == 'src/test.py'
        assert pinned.pinned_at > 0
        assert pinned.last_modified > 0

    def test_update_last_modified(self) -> None:
        """Test updating last modified timestamp."""
        pinned = PinnedFile.create('src/test.py')
        original_timestamp = pinned.last_modified

        # Small delay
        import time

        time.sleep(0.01)

        pinned.update_last_modified()
        assert pinned.last_modified > original_timestamp

    def test_serialization(self) -> None:
        """Test pinned file serialization and deserialization."""
        pinned = PinnedFile.create('src/test.py')

        # Serialize
        pinned_dict = pinned.to_dict()
        assert isinstance(pinned_dict, dict)
        assert pinned_dict['file_path'] == 'src/test.py'

        # Deserialize
        restored = PinnedFile.from_dict(pinned_dict)
        assert restored.file_path == pinned.file_path
        assert restored.pinned_at == pinned.pinned_at


class TestPinnedFileStorage:
    """Test PinnedFileStorage operations."""

    @pytest.fixture
    def temp_root(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_add_file(self, temp_root: Path) -> None:
        """Test adding a file to the pinned list."""
        storage = PinnedFileStorage(temp_root)

        # Create a test file
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')

        # Add file (relative path)
        result = storage.add('test.py')
        assert result is True

        # List files
        pinned = storage.list_all()
        assert len(pinned) == 1
        assert pinned[0].file_path == 'test.py'

    def test_add_nonexistent_file(self, temp_root: Path) -> None:
        """Test adding a non-existent file."""
        storage = PinnedFileStorage(temp_root)

        # Try to add non-existent file
        result = storage.add('nonexistent.py')
        assert result is False

    def test_add_duplicate_file(self, temp_root: Path) -> None:
        """Test adding a file that's already pinned."""
        storage = PinnedFileStorage(temp_root)

        # Create a test file
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')

        # Add file twice
        storage.add('test.py')
        result = storage.add('test.py')
        assert result is False

        # Should still have only one entry
        pinned = storage.list_all()
        assert len(pinned) == 1

    def test_remove_file(self, temp_root: Path) -> None:
        """Test removing a file from the pinned list."""
        storage = PinnedFileStorage(temp_root)

        # Create and add a test file
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')
        storage.add('test.py')

        # Remove file
        result = storage.remove('test.py')
        assert result is True

        # List files
        pinned = storage.list_all()
        assert len(pinned) == 0

    def test_remove_non_pinned_file(self, temp_root: Path) -> None:
        """Test removing a file that's not pinned."""
        storage = PinnedFileStorage(temp_root)

        # Try to remove non-pinned file
        result = storage.remove('test.py')
        assert result is False

    def test_list_all(self, temp_root: Path) -> None:
        """Test listing all pinned files."""
        storage = PinnedFileStorage(temp_root)

        # Create and add multiple test files
        for i in range(3):
            test_file = temp_root / f'test{i}.py'
            test_file.write_text(f'content {i}')
            storage.add(f'test{i}.py')

        # List files
        pinned = storage.list_all()
        assert len(pinned) == 3

    def test_clear_all(self, temp_root: Path) -> None:
        """Test clearing all pinned files."""
        storage = PinnedFileStorage(temp_root)

        # Create and add test files
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')
        storage.add('test.py')

        # Clear all
        storage.clear_all()
        pinned = storage.list_all()
        assert len(pinned) == 0

    def test_update_last_modified(self, temp_root: Path) -> None:
        """Test updating last modified timestamp."""
        storage = PinnedFileStorage(temp_root)

        # Create and add a test file
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')
        storage.add('test.py')

        # Get original timestamp
        pinned = storage.list_all()
        original_timestamp = pinned[0].last_modified

        # Small delay
        import time

        time.sleep(0.01)

        # Update timestamp
        result = storage.update_last_modified('test.py')
        assert result is True

        # Check updated timestamp
        pinned = storage.list_all()
        assert pinned[0].last_modified > original_timestamp

    def test_is_pinned(self, temp_root: Path) -> None:
        """Test checking if a file is pinned."""
        storage = PinnedFileStorage(temp_root)

        # Create and add a test file
        test_file = temp_root / 'test.py'
        test_file.write_text('test content')
        storage.add('test.py')

        # Check if pinned
        assert storage.is_pinned('test.py') is True
        assert storage.is_pinned('other.py') is False

    def test_missing_file(self, temp_root: Path) -> None:
        """Test reading from missing storage file."""
        storage = PinnedFileStorage(temp_root)
        pinned = storage.list_all()
        assert pinned == []

    def test_corrupted_file(self, temp_root: Path) -> None:
        """Test reading from corrupted storage file."""
        storage = PinnedFileStorage(temp_root)

        # Write corrupted JSON
        storage_file = storage.storage_file
        storage_file.write_text('invalid json')

        # Should return empty list
        pinned = storage.list_all()
        assert pinned == []


class TestFileWatcher:
    """Test file watcher functionality."""

    @pytest.fixture
    def temp_root(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_file_watcher_initialization(self, temp_root: Path) -> None:
        """Test file watcher initialization."""
        from teaagent.memory.file_watcher import WATCHDOG_AVAILABLE, FileWatcher

        if not WATCHDOG_AVAILABLE:
            pytest.skip('watchdog library not available')

        callback_called = []

        def test_callback(file_path: str, event_type: str) -> None:
            callback_called.append((file_path, event_type))

        watcher = FileWatcher(
            root=temp_root,
            callback=test_callback,
            debounce_ms=100,
        )

        assert watcher.root == temp_root.resolve()
        assert watcher.callback == test_callback
        assert watcher.debounce_ms == 100
        assert watcher.is_running() is False

    def test_file_watcher_start_stop(self, temp_root: Path) -> None:
        """Test starting and stopping the file watcher."""
        from teaagent.memory.file_watcher import WATCHDOG_AVAILABLE, FileWatcher

        if not WATCHDOG_AVAILABLE:
            pytest.skip('watchdog library not available')

        def test_callback(file_path: str, event_type: str) -> None:
            pass

        watcher = FileWatcher(
            root=temp_root,
            callback=test_callback,
        )

        # Start watcher
        watcher.start()
        assert watcher.is_running() is True

        # Stop watcher
        watcher.stop()
        assert watcher.is_running() is False

    def test_update_watched_files(self, temp_root: Path) -> None:
        """Test updating the set of watched files."""
        from teaagent.memory.file_watcher import WATCHDOG_AVAILABLE, FileWatcher

        if not WATCHDOG_AVAILABLE:
            pytest.skip('watchdog library not available')

        def test_callback(file_path: str, event_type: str) -> None:
            pass

        watcher = FileWatcher(
            root=temp_root,
            callback=test_callback,
        )

        # Update watched files
        watcher.update_watched_files({'test.py', 'other.py'})
        assert watcher.watched_files == {'test.py', 'other.py'}

        # Update again
        watcher.update_watched_files({'new.py'})
        assert watcher.watched_files == {'new.py'}
