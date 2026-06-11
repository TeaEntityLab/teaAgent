"""Tests for update application mechanism (TASK-H6-003-03)."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest

from teaagent.update.installer import (
    UpdateDownloader,
    UpdateInstaller,
    UpdateManager,
    UpdatePackage,
    UpdateProgress,
    UpdateStatus,
)


@pytest.fixture
def downloader():
    """Fixture for UpdateDownloader."""
    return UpdateDownloader()


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    with TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture
def install_dir(temp_dir):
    """Fixture for install directory."""
    install_path = Path(temp_dir) / 'install'
    install_path.mkdir()
    return install_path


@pytest.fixture
def installer(install_dir):
    """Fixture for UpdateInstaller."""
    return UpdateInstaller(install_dir)


@pytest.fixture
def manager(install_dir):
    """Fixture for UpdateManager."""
    return UpdateManager(install_dir)


def test_to_dict_and_from_dict():
    """Test serialization."""
    package = UpdatePackage(
        version='1.2.3',
        download_url='https://example.com/package.tar.gz',
        checksum='abc123',
        size_bytes=1024,
    )

    data = package.to_dict()
    restored = UpdatePackage.from_dict(data)

    assert restored.version == package.version
    assert restored.download_url == package.download_url


def test_update_progress_to_dict():
    """Test serialization."""
    progress = UpdateProgress(
        status=UpdateStatus.DOWNLOADING,
        progress_percentage=50.0,
        current_step='Downloading',
    )

    data = progress.to_dict()

    assert data['status'] == 'downloading'
    assert data['progress_percentage'] == 50.0


def test_verify_checksum(downloader, temp_dir):
    """Test checksum verification."""
    # Create test file
    test_file = Path(temp_dir) / 'test.txt'
    test_file.write_bytes(b'test content')

    # Calculate checksum
    import hashlib

    sha256_hash = hashlib.sha256()
    with test_file.open('rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256_hash.update(chunk)
    expected_checksum = sha256_hash.hexdigest()

    # Verify
    result = downloader.verify_checksum(test_file, expected_checksum)
    assert result

    # Test with wrong checksum
    result = downloader.verify_checksum(test_file, 'wrong_checksum')
    assert not result


def test_create_backup(installer):
    """Test creating backup."""
    # Create some files in install dir
    (installer.install_dir / 'file1.txt').write_text('content1')
    (installer.install_dir / 'file2.txt').write_text('content2')

    backup_dir = installer.create_backup()

    assert backup_dir.exists()
    assert (backup_dir / 'current').exists()
    assert (backup_dir / 'current' / 'file1.txt').exists()
    assert (backup_dir / 'backup_metadata.json').exists()


def test_create_backup_empty_install(installer):
    """Test creating backup with empty install directory."""
    backup_dir = installer.create_backup()

    assert backup_dir.exists()
    assert (backup_dir / 'backup_metadata.json').exists()


def test_rollback(installer):
    """Test rollback to backup."""
    # Create initial files
    (installer.install_dir / 'file1.txt').write_text('original')

    # Create backup
    backup_dir = installer.create_backup()

    # Modify install
    (installer.install_dir / 'file1.txt').write_text('modified')
    (installer.install_dir / 'file2.txt').write_text('new file')

    # Rollback
    installer.rollback(backup_dir)

    # Verify restored
    assert (installer.install_dir / 'file1.txt').read_text() == 'original'
    assert not (installer.install_dir / 'file2.txt').exists()


def test_cleanup_backup(installer):
    """Test cleaning up backup."""
    # Create backup
    backup_dir = installer.create_backup()

    # Save backup info
    backup_info = {'backup_dir': str(backup_dir)}
    (installer.install_dir / '.teaagent_backup.json').write_text(
        json.dumps(backup_info),
        encoding='utf-8',
    )

    # Cleanup
    installer.cleanup_backup()

    # Verify cleanup
    assert not backup_dir.exists()
    assert not (installer.install_dir / '.teaagent_backup.json').exists()


def test_init(manager):
    """Test update manager initialization."""
    assert manager.install_dir.resolve() == manager.install_dir.resolve()
    assert manager.downloader is not None
    assert manager.installer is not None


@patch('teaagent.update.installer.UpdateDownloader')
@patch('teaagent.update.installer.UpdateInstaller')
def test_apply_update_success(mock_installer_class, mock_downloader_class, install_dir):
    """Test successful update application."""
    # Mock downloader
    mock_downloader = Mock()
    mock_downloader_class.return_value = mock_downloader
    mock_downloader.download_package.return_value = Path('/tmp/package.tar.gz')

    # Mock installer
    mock_installer = Mock()
    mock_installer_class.return_value = mock_installer

    # Create manager with mocks
    manager = UpdateManager(install_dir)

    # Apply update
    package = UpdatePackage(
        version='1.2.3',
        download_url='https://example.com/package.tar.gz',
        checksum='abc123',
    )

    progress = manager.apply_update(package)

    assert progress.status == UpdateStatus.COMPLETED


def test_rollback_last_update(manager, temp_dir):
    """Test rolling back last update."""
    # Create backup info
    backup_dir = Path(temp_dir) / 'backup'
    backup_dir.mkdir()
    (backup_dir / 'current').mkdir()
    (backup_dir / 'current' / 'file1.txt').write_text('original')

    backup_info = {'backup_dir': str(backup_dir)}
    (manager.install_dir / '.teaagent_backup.json').write_text(
        json.dumps(backup_info),
        encoding='utf-8',
    )

    # Modify install
    (manager.install_dir / 'file1.txt').write_text('modified')

    # Rollback
    progress = manager.rollback_last_update()

    assert progress.status == UpdateStatus.ROLLED_BACK
    assert (manager.install_dir / 'file1.txt').read_text() == 'original'


def test_rollback_no_backup(manager):
    """Test rollback when no backup exists."""
    progress = manager.rollback_last_update()

    assert progress.status == UpdateStatus.FAILED
    assert 'No backup found' in progress.error_message
