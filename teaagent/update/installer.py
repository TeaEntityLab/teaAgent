"""Update application with rollback mechanism (TASK-H6-003-03).

experimental — unwired

This module provides update download, installation, and rollback functionality
for safe and reliable updates.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


class UpdateStatus(str, Enum):
    """Status of update process."""

    DOWNLOADING = 'downloading'
    VERIFYING = 'verifying'
    INSTALLING = 'installing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ROLLED_BACK = 'rolled_back'


@dataclass
class UpdatePackage:
    """A downloadable update package."""

    version: str
    download_url: str
    checksum: str
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'download_url': self.download_url,
            'checksum': self.checksum,
            'size_bytes': self.size_bytes,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'UpdatePackage':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            download_url=data['download_url'],
            checksum=data['checksum'],
            size_bytes=data.get('size_bytes', 0),
            metadata=data.get('metadata', {}),
        )


@dataclass
class UpdateProgress:
    """Progress of update process."""

    status: UpdateStatus
    progress_percentage: float = 0.0
    current_step: str = ''
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'status': self.status.value,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'error_message': self.error_message,
            'metadata': self.metadata,
        }


class UpdateDownloader:
    """Downloader for update packages."""

    def __init__(self) -> None:
        """Initialize the update downloader."""
        pass

    def download_package(
        self,
        package: UpdatePackage,
        output_path: str | Path,
        progress_callback: Optional[Callable] = None,
    ) -> Path:
        """Download an update package.

        Args:
            package: Package to download.
            output_path: Path to save downloaded package.
            progress_callback: Optional callback for progress updates.

        Returns:
            Path to downloaded package.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            request = Request(package.download_url, headers={'User-Agent': 'teaagent'})

            with urlopen(request, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with output_path.open('wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress)

            # Verify checksum
            if not self.verify_checksum(output_path, package.checksum):
                output_path.unlink()
                raise ValueError('Checksum verification failed')

            return output_path

        except (URLError, ValueError):
            if output_path.exists():
                output_path.unlink()
            raise

    def verify_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Verify file checksum.

        Args:
            file_path: Path to file.
            expected_checksum: Expected SHA256 checksum.

        Returns:
            True if checksum matches, False otherwise.
        """
        sha256_hash = hashlib.sha256()
        with file_path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest() == expected_checksum


class UpdateInstaller:
    """Installer for update packages."""

    def __init__(self, install_dir: str | Path) -> None:
        """Initialize the update installer.

        Args:
            install_dir: Directory where teaagent is installed.
        """
        self.install_dir = Path(install_dir).resolve()

    def create_backup(self) -> Path:
        """Create a backup of current installation.

        Returns:
            Path to backup directory.
        """
        backup_dir = Path(tempfile.mkdtemp(prefix='teaagent-backup-'))

        # Copy entire installation to backup
        if self.install_dir.exists():
            shutil.copytree(
                self.install_dir, backup_dir / 'current', dirs_exist_ok=True
            )

        # Save backup metadata
        metadata = {
            'original_install_dir': str(self.install_dir),
            'backup_created_at': None,  # Would be timestamp
        }
        (backup_dir / 'backup_metadata.json').write_text(
            json.dumps(metadata, indent=2),
            encoding='utf-8',
        )

        return backup_dir

    def install_package(
        self,
        package_path: str | Path,
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """Install an update package.

        Args:
            package_path: Path to downloaded package.
            progress_callback: Optional callback for progress updates.
        """
        package_path = Path(package_path)

        if progress_callback:
            progress_callback(0)

        # Create backup
        backup_dir = self.create_backup()

        if progress_callback:
            progress_callback(25)

        try:
            # Extract package (placeholder - assumes tar.gz)
            import tarfile

            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(self.install_dir)

            if progress_callback:
                progress_callback(75)

            # Save backup location for rollback
            backup_info = {
                'backup_dir': str(backup_dir),
                'package_version': None,  # Would be extracted from package
            }
            (self.install_dir / '.teaagent_backup.json').write_text(
                json.dumps(backup_info, indent=2),
                encoding='utf-8',
            )

            if progress_callback:
                progress_callback(100)

        except Exception:
            # Rollback on failure
            self.rollback(backup_dir)
            raise

    def rollback(self, backup_dir: str | Path) -> None:
        """Rollback to backup.

        Args:
            backup_dir: Path to backup directory.
        """
        backup_dir = Path(backup_dir)
        current_backup = backup_dir / 'current'

        if not current_backup.exists():
            raise ValueError('Backup directory not found')

        # Remove current installation
        if self.install_dir.exists():
            shutil.rmtree(self.install_dir)

        # Restore from backup
        shutil.copytree(current_backup, self.install_dir)

        # Clean up backup
        shutil.rmtree(backup_dir)

    def cleanup_backup(self) -> None:
        """Clean up backup directory after successful installation."""
        backup_info_path = self.install_dir / '.teaagent_backup.json'

        if backup_info_path.exists():
            backup_info = json.loads(backup_info_path.read_text(encoding='utf-8'))
            backup_dir = Path(backup_info.get('backup_dir', ''))

            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            backup_info_path.unlink()


class UpdateManager:
    """Manager for update process."""

    def __init__(self, install_dir: str | Path) -> None:
        """Initialize the update manager.

        Args:
            install_dir: Directory where teaagent is installed.
        """
        self.install_dir = Path(install_dir).resolve()
        self.downloader = UpdateDownloader()
        self.installer = UpdateInstaller(install_dir)

    def apply_update(
        self,
        package: UpdatePackage,
        progress_callback: Optional[Callable] = None,
    ) -> UpdateProgress:
        """Apply an update package.

        Args:
            package: Package to install.
            progress_callback: Optional callback for progress updates.

        Returns:
            Update progress.
        """
        progress = UpdateProgress(status=UpdateStatus.DOWNLOADING)

        try:
            # Download package
            if progress_callback:
                progress_callback(progress)

            temp_dir = Path(tempfile.mkdtemp(prefix='teaagent-update-'))
            package_path = temp_dir / 'package.tar.gz'

            self.downloader.download_package(
                package,
                package_path,
                lambda p: self._update_progress(progress, p, progress_callback),
            )

            progress.status = UpdateStatus.VERIFYING
            if progress_callback:
                progress_callback(progress)

            # Install package
            progress.status = UpdateStatus.INSTALLING
            if progress_callback:
                progress_callback(progress)

            self.installer.install_package(
                package_path,
                lambda p: self._update_progress(progress, p, progress_callback),
            )

            progress.status = UpdateStatus.COMPLETED
            progress.progress_percentage = 100.0
            if progress_callback:
                progress_callback(progress)

            # Cleanup
            shutil.rmtree(temp_dir)
            self.installer.cleanup_backup()

            return progress

        except Exception as e:
            progress.status = UpdateStatus.FAILED
            progress.error_message = str(e)
            if progress_callback:
                progress_callback(progress)
            return progress

    def _update_progress(
        self,
        progress: UpdateProgress,
        percentage: float,
        callback: Optional[Callable],
    ) -> None:
        """Update progress and call callback.

        Args:
            progress: Progress object to update.
            percentage: Progress percentage.
            callback: Optional callback.
        """
        progress.progress_percentage = percentage
        if callback:
            callback(progress)

    def rollback_last_update(self) -> UpdateProgress:
        """Rollback the last update.

        Returns:
            Update progress.
        """
        progress = UpdateProgress(status=UpdateStatus.ROLLED_BACK)

        try:
            backup_info_path = self.install_dir / '.teaagent_backup.json'

            if not backup_info_path.exists():
                progress.error_message = 'No backup found'
                progress.status = UpdateStatus.FAILED
                return progress

            backup_info = json.loads(backup_info_path.read_text(encoding='utf-8'))
            backup_dir = Path(backup_info.get('backup_dir', ''))

            if not backup_dir.exists():
                progress.error_message = 'Backup directory not found'
                progress.status = UpdateStatus.FAILED
                return progress

            self.installer.rollback(backup_dir)

            progress.progress_percentage = 100.0
            return progress

        except Exception as e:
            progress.status = UpdateStatus.FAILED
            progress.error_message = str(e)
            return progress
