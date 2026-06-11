"""Tests for in-memory VFS sandbox (TASK-010)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from teaagent.git_sandbox import VFSSandbox


def test_vfs_write_and_read() -> None:
    """Test writing and reading files in VFS."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Hello, World!')

        content = vfs.read_file('test.txt')
        assert content == 'Hello, World!'


def test_vfs_read_fallback_to_disk() -> None:
    """Test reading from disk when file not in memory."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'disk.txt'
        disk_file.write_text('Disk content')

        vfs = VFSSandbox(tmp)
        content = vfs.read_file('disk.txt')
        assert content == 'Disk content'


def test_vfs_write_overrides_disk() -> None:
    """Test that memory writes override disk files."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'test.txt'
        disk_file.write_text('Disk content')

        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Memory content')

        content = vfs.read_file('test.txt')
        assert content == 'Memory content'


def test_vfs_delete_file() -> None:
    """Test deleting files in VFS."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Content')

        vfs.delete_file('test.txt')

        with pytest.raises(FileNotFoundError):
            vfs.read_file('test.txt')


def test_vfs_delete_disk_file() -> None:
    """Test deleting disk files via VFS."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'test.txt'
        disk_file.write_text('Disk content')

        vfs = VFSSandbox(tmp)
        vfs.delete_file('test.txt')

        # Should be marked as deleted in VFS
        with pytest.raises(FileNotFoundError):
            vfs.read_file('test.txt')


def test_vfs_file_exists_memory() -> None:
    """Test file_exists for memory files."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Content')

        assert vfs.file_exists('test.txt')


def test_vfs_file_exists_disk() -> None:
    """Test file_exists for disk files."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'test.txt'
        disk_file.write_text('Content')

        vfs = VFSSandbox(tmp)
        assert vfs.file_exists('test.txt')


def test_vfs_file_exists_deleted() -> None:
    """Test file_exists for deleted files."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'test.txt'
        disk_file.write_text('Content')

        vfs = VFSSandbox(tmp)
        vfs.delete_file('test.txt')

        assert not vfs.file_exists('test.txt')


def test_vfs_list_files() -> None:
    """Test listing files in VFS."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test1.txt', 'Content 1')
        vfs.write_file('test2.txt', 'Content 2')

        files = vfs.list_files()
        assert len(files) == 2
        assert 'test1.txt' in files
        assert 'test2.txt' in files


def test_vfs_flush_to_disk() -> None:
    """Test flushing memory files to disk."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Memory content')

        results = vfs.flush_to_disk()

        assert results.get('test.txt', False)

        # Verify file exists on disk
        disk_file = Path(tmp) / 'test.txt'
        assert disk_file.exists()
        assert disk_file.read_text() == 'Memory content'


def test_vfs_flush_deletions() -> None:
    """Test flushing deletions to disk."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create file on disk
        disk_file = Path(tmp) / 'test.txt'
        disk_file.write_text('Disk content')

        vfs = VFSSandbox(tmp)
        vfs.delete_file('test.txt')

        results = vfs.flush_to_disk()

        assert results.get('test.txt', False)

        # Verify file deleted from disk
        assert not disk_file.exists()


def test_vfs_clear() -> None:
    """Test clearing VFS."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test1.txt', 'Content 1')
        vfs.write_file('test2.txt', 'Content 2')
        vfs.delete_file('test3.txt')

        vfs.clear()

        assert len(vfs.list_files()) == 0


def test_vfs_get_memory_size() -> None:
    """Test getting memory size."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test1.txt', 'Hello')  # 5 bytes
        vfs.write_file('test2.txt', 'World')  # 5 bytes

        size = vfs.get_memory_size()
        assert size == 10


def test_vfs_write_overwrite() -> None:
    """Test overwriting existing memory file."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('test.txt', 'Original')
        vfs.write_file('test.txt', 'Updated')

        content = vfs.read_file('test.txt')
        assert content == 'Updated'


def test_vfs_read_nonexistent() -> None:
    """Test reading non-existent file."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)

        with pytest.raises(FileNotFoundError):
            vfs.read_file('nonexistent.txt')


def test_vfs_nested_paths() -> None:
    """Test handling nested directory paths."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('subdir/test.txt', 'Nested content')

        content = vfs.read_file('subdir/test.txt')
        assert content == 'Nested content'


def test_vfs_flush_creates_directories() -> None:
    """Test that flush creates nested directories."""
    with tempfile.TemporaryDirectory() as tmp:
        vfs = VFSSandbox(tmp)
        vfs.write_file('subdir/nested/test.txt', 'Content')

        vfs.flush_to_disk()

        # Verify nested directory created
        nested_file = Path(tmp) / 'subdir' / 'nested' / 'test.txt'
        assert nested_file.exists()
        assert nested_file.read_text() == 'Content'
