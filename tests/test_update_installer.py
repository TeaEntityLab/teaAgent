"""Tests for update application mechanism (TASK-H6-003-03)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from teaagent.update.installer import (
    UpdateDownloader,
    UpdateInstaller,
    UpdateManager,
    UpdatePackage,
    UpdateProgress,
    UpdateStatus,
)


class TestUpdatePackage(unittest.TestCase):
    """Test update package."""

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        package = UpdatePackage(
            version='1.2.3',
            download_url='https://example.com/package.tar.gz',
            checksum='abc123',
            size_bytes=1024,
        )

        data = package.to_dict()
        restored = UpdatePackage.from_dict(data)

        self.assertEqual(restored.version, package.version)
        self.assertEqual(restored.download_url, package.download_url)


class TestUpdateProgress(unittest.TestCase):
    """Test update progress."""

    def test_to_dict(self):
        """Test serialization."""
        progress = UpdateProgress(
            status=UpdateStatus.DOWNLOADING,
            progress_percentage=50.0,
            current_step='Downloading',
        )

        data = progress.to_dict()

        self.assertEqual(data['status'], 'downloading')
        self.assertEqual(data['progress_percentage'], 50.0)


class TestUpdateDownloader(unittest.TestCase):
    """Test update downloader."""

    def setUp(self):
        """Set up test fixtures."""
        self.downloader = UpdateDownloader()
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_verify_checksum(self):
        """Test checksum verification."""
        # Create test file
        test_file = Path(self.temp_dir.name) / 'test.txt'
        test_file.write_bytes(b'test content')

        # Calculate checksum
        import hashlib

        sha256_hash = hashlib.sha256()
        with test_file.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)
        expected_checksum = sha256_hash.hexdigest()

        # Verify
        result = self.downloader.verify_checksum(test_file, expected_checksum)
        self.assertTrue(result)

        # Test with wrong checksum
        result = self.downloader.verify_checksum(test_file, 'wrong_checksum')
        self.assertFalse(result)


class TestUpdateInstaller(unittest.TestCase):
    """Test update installer."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.install_dir = Path(self.temp_dir.name) / 'install'
        self.install_dir.mkdir()
        self.installer = UpdateInstaller(self.install_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_create_backup(self):
        """Test creating backup."""
        # Create some files in install dir
        (self.install_dir / 'file1.txt').write_text('content1')
        (self.install_dir / 'file2.txt').write_text('content2')

        backup_dir = self.installer.create_backup()

        self.assertTrue(backup_dir.exists())
        self.assertTrue((backup_dir / 'current').exists())
        self.assertTrue((backup_dir / 'current' / 'file1.txt').exists())
        self.assertTrue((backup_dir / 'backup_metadata.json').exists())

    def test_create_backup_empty_install(self):
        """Test creating backup with empty install directory."""
        backup_dir = self.installer.create_backup()

        self.assertTrue(backup_dir.exists())
        self.assertTrue((backup_dir / 'backup_metadata.json').exists())

    def test_rollback(self):
        """Test rollback to backup."""
        # Create initial files
        (self.install_dir / 'file1.txt').write_text('original')

        # Create backup
        backup_dir = self.installer.create_backup()

        # Modify install
        (self.install_dir / 'file1.txt').write_text('modified')
        (self.install_dir / 'file2.txt').write_text('new file')

        # Rollback
        self.installer.rollback(backup_dir)

        # Verify restored
        self.assertEqual((self.install_dir / 'file1.txt').read_text(), 'original')
        self.assertFalse((self.install_dir / 'file2.txt').exists())

    def test_cleanup_backup(self):
        """Test cleaning up backup."""
        # Create backup
        backup_dir = self.installer.create_backup()

        # Save backup info
        backup_info = {'backup_dir': str(backup_dir)}
        (self.install_dir / '.teaagent_backup.json').write_text(
            json.dumps(backup_info),
            encoding='utf-8',
        )

        # Cleanup
        self.installer.cleanup_backup()

        # Verify cleanup
        self.assertFalse(backup_dir.exists())
        self.assertFalse((self.install_dir / '.teaagent_backup.json').exists())


class TestUpdateManager(unittest.TestCase):
    """Test update manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = TemporaryDirectory()
        self.install_dir = Path(self.temp_dir.name) / 'install'
        self.install_dir.mkdir()
        self.manager = UpdateManager(self.install_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_init(self):
        """Test update manager initialization."""
        self.assertEqual(self.manager.install_dir.resolve(), self.install_dir.resolve())
        self.assertIsNotNone(self.manager.downloader)
        self.assertIsNotNone(self.manager.installer)

    @patch('teaagent.update.installer.UpdateDownloader')
    @patch('teaagent.update.installer.UpdateInstaller')
    def test_apply_update_success(self, mock_installer_class, mock_downloader_class):
        """Test successful update application."""
        # Mock downloader
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download_package.return_value = Path('/tmp/package.tar.gz')

        # Mock installer
        mock_installer = Mock()
        mock_installer_class.return_value = mock_installer

        # Create manager with mocks
        manager = UpdateManager(self.install_dir)

        # Apply update
        package = UpdatePackage(
            version='1.2.3',
            download_url='https://example.com/package.tar.gz',
            checksum='abc123',
        )

        progress = manager.apply_update(package)

        self.assertEqual(progress.status, UpdateStatus.COMPLETED)

    def test_rollback_last_update(self):
        """Test rolling back last update."""
        # Create backup info
        backup_dir = Path(self.temp_dir.name) / 'backup'
        backup_dir.mkdir()
        (backup_dir / 'current').mkdir()
        (backup_dir / 'current' / 'file1.txt').write_text('original')

        backup_info = {'backup_dir': str(backup_dir)}
        (self.install_dir / '.teaagent_backup.json').write_text(
            json.dumps(backup_info),
            encoding='utf-8',
        )

        # Modify install
        (self.install_dir / 'file1.txt').write_text('modified')

        # Rollback
        progress = self.manager.rollback_last_update()

        self.assertEqual(progress.status, UpdateStatus.ROLLED_BACK)
        self.assertEqual((self.install_dir / 'file1.txt').read_text(), 'original')

    def test_rollback_no_backup(self):
        """Test rollback when no backup exists."""
        progress = self.manager.rollback_last_update()

        self.assertEqual(progress.status, UpdateStatus.FAILED)
        self.assertIn('No backup found', progress.error_message)


if __name__ == '__main__':
    unittest.main()
