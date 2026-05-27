"""Tests for in-memory VFS sandbox (TASK-010)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.git_sandbox import VFSSandbox


class VFSSandboxTests(unittest.TestCase):
    def test_vfs_write_and_read(self) -> None:
        """Test writing and reading files in VFS."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Hello, World!')

            content = vfs.read_file('test.txt')
            self.assertEqual(content, 'Hello, World!')

    def test_vfs_read_fallback_to_disk(self) -> None:
        """Test reading from disk when file not in memory."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'disk.txt'
            disk_file.write_text('Disk content')

            vfs = VFSSandbox(tmp)
            content = vfs.read_file('disk.txt')
            self.assertEqual(content, 'Disk content')

    def test_vfs_write_overrides_disk(self) -> None:
        """Test that memory writes override disk files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'test.txt'
            disk_file.write_text('Disk content')

            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Memory content')

            content = vfs.read_file('test.txt')
            self.assertEqual(content, 'Memory content')

    def test_vfs_delete_file(self) -> None:
        """Test deleting files in VFS."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Content')

            vfs.delete_file('test.txt')

            with self.assertRaises(FileNotFoundError):
                vfs.read_file('test.txt')

    def test_vfs_delete_disk_file(self) -> None:
        """Test deleting disk files via VFS."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'test.txt'
            disk_file.write_text('Disk content')

            vfs = VFSSandbox(tmp)
            vfs.delete_file('test.txt')

            # Should be marked as deleted in VFS
            with self.assertRaises(FileNotFoundError):
                vfs.read_file('test.txt')

    def test_vfs_file_exists_memory(self) -> None:
        """Test file_exists for memory files."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Content')

            self.assertTrue(vfs.file_exists('test.txt'))

    def test_vfs_file_exists_disk(self) -> None:
        """Test file_exists for disk files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'test.txt'
            disk_file.write_text('Content')

            vfs = VFSSandbox(tmp)
            self.assertTrue(vfs.file_exists('test.txt'))

    def test_vfs_file_exists_deleted(self) -> None:
        """Test file_exists for deleted files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'test.txt'
            disk_file.write_text('Content')

            vfs = VFSSandbox(tmp)
            vfs.delete_file('test.txt')

            self.assertFalse(vfs.file_exists('test.txt'))

    def test_vfs_list_files(self) -> None:
        """Test listing files in VFS."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test1.txt', 'Content 1')
            vfs.write_file('test2.txt', 'Content 2')

            files = vfs.list_files()
            self.assertEqual(len(files), 2)
            self.assertIn('test1.txt', files)
            self.assertIn('test2.txt', files)

    def test_vfs_flush_to_disk(self) -> None:
        """Test flushing memory files to disk."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Memory content')

            results = vfs.flush_to_disk()

            self.assertTrue(results.get('test.txt', False))

            # Verify file exists on disk
            disk_file = Path(tmp) / 'test.txt'
            self.assertTrue(disk_file.exists())
            self.assertEqual(disk_file.read_text(), 'Memory content')

    def test_vfs_flush_deletions(self) -> None:
        """Test flushing deletions to disk."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create file on disk
            disk_file = Path(tmp) / 'test.txt'
            disk_file.write_text('Disk content')

            vfs = VFSSandbox(tmp)
            vfs.delete_file('test.txt')

            results = vfs.flush_to_disk()

            self.assertTrue(results.get('test.txt', False))

            # Verify file deleted from disk
            self.assertFalse(disk_file.exists())

    def test_vfs_clear(self) -> None:
        """Test clearing VFS."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test1.txt', 'Content 1')
            vfs.write_file('test2.txt', 'Content 2')
            vfs.delete_file('test3.txt')

            vfs.clear()

            self.assertEqual(len(vfs.list_files()), 0)

    def test_vfs_get_memory_size(self) -> None:
        """Test getting memory size."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test1.txt', 'Hello')  # 5 bytes
            vfs.write_file('test2.txt', 'World')  # 5 bytes

            size = vfs.get_memory_size()
            self.assertEqual(size, 10)

    def test_vfs_write_overwrite(self) -> None:
        """Test overwriting existing memory file."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('test.txt', 'Original')
            vfs.write_file('test.txt', 'Updated')

            content = vfs.read_file('test.txt')
            self.assertEqual(content, 'Updated')

    def test_vfs_read_nonexistent(self) -> None:
        """Test reading non-existent file."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)

            with self.assertRaises(FileNotFoundError):
                vfs.read_file('nonexistent.txt')

    def test_vfs_nested_paths(self) -> None:
        """Test handling nested directory paths."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('subdir/test.txt', 'Nested content')

            content = vfs.read_file('subdir/test.txt')
            self.assertEqual(content, 'Nested content')

    def test_vfs_flush_creates_directories(self) -> None:
        """Test that flush creates nested directories."""
        with tempfile.TemporaryDirectory() as tmp:
            vfs = VFSSandbox(tmp)
            vfs.write_file('subdir/nested/test.txt', 'Content')

            vfs.flush_to_disk()

            # Verify nested directory created
            nested_file = Path(tmp) / 'subdir' / 'nested' / 'test.txt'
            self.assertTrue(nested_file.exists())
            self.assertEqual(nested_file.read_text(), 'Content')


if __name__ == '__main__':
    unittest.main()
