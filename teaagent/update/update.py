"""Update check mechanism for teaagent (TASK-H6-003-01).

This module provides version checking, update server communication, and
version comparison for detecting available updates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


class UpdateChannel(str, Enum):
    """Update channels for version releases."""

    STABLE = 'stable'  # Stable releases only
    BETA = 'beta'  # Stable and beta releases
    ALPHA = 'alpha'  # All releases including alpha


@dataclass
class Version:
    """A version number."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __str__(self) -> str:
        """Convert to string representation."""
        version_str = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease:
            version_str += f'-{self.prerelease}'
        if self.build:
            version_str += f'+{self.build}'
        return version_str

    @classmethod
    def from_string(cls, version_str: str) -> 'Version':
        """Parse version from string.

        Args:
            version_str: Version string to parse.

        Returns:
            Version object.
        """
        # Parse version string (e.g., "1.2.3-beta+build123")
        parts = version_str.split('+')
        build = parts[1] if len(parts) > 1 else None

        main_part = parts[0]
        prerelease_parts = main_part.split('-')
        prerelease = prerelease_parts[1] if len(prerelease_parts) > 1 else None

        version_parts = prerelease_parts[0].split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        patch = int(version_parts[2]) if len(version_parts) > 2 else 0

        return cls(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
            build=build,
        )

    def __lt__(self, other: 'Version') -> bool:
        """Compare versions (less than)."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch

        # Compare prerelease (no prerelease > any prerelease)
        if self.prerelease is None and other.prerelease is not None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease

        return False

    def __eq__(self, other: object) -> bool:
        """Compare versions (equal)."""
        if not isinstance(other, Version):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
            and self.build == other.build
        )

    def __le__(self, other: 'Version') -> bool:
        """Compare versions (less than or equal)."""
        return self < other or self == other


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: Version
    channel: UpdateChannel
    release_date: Optional[str] = None
    download_url: Optional[str] = None
    checksum: Optional[str] = None
    changelog: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': str(self.version),
            'channel': self.channel.value,
            'release_date': self.release_date,
            'download_url': self.download_url,
            'checksum': self.checksum,
            'changelog': self.changelog,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'UpdateInfo':
        """Create from dictionary."""
        return cls(
            version=Version.from_string(data['version']),
            channel=UpdateChannel(data['channel']),
            release_date=data.get('release_date'),
            download_url=data.get('download_url'),
            checksum=data.get('checksum'),
            changelog=data.get('changelog'),
            metadata=data.get('metadata', {}),
        )


class UpdateServer:
    """Update server for checking available updates."""

    def __init__(self, base_url: str = 'https://api.teaagent.dev') -> None:
        """Initialize the update server.

        Args:
            base_url: Base URL for update server.
        """
        self.base_url = base_url.rstrip('/')

    def check_for_updates(
        self,
        current_version: str,
        channel: UpdateChannel = UpdateChannel.STABLE,
    ) -> Optional[UpdateInfo]:
        """Check for available updates.

        Args:
            current_version: Current version string.
            channel: Update channel to check.

        Returns:
            UpdateInfo if update available, None otherwise.
        """
        try:
            current = Version.from_string(current_version)

            # Fetch latest version from server
            url = f'{self.base_url}/updates/latest?channel={channel.value}'
            request = Request(url, headers={'User-Agent': 'teaagent'})

            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            latest = Version.from_string(data['version'])

            # Check if update available
            if latest > current:
                return UpdateInfo(
                    version=latest,
                    channel=channel,
                    release_date=data.get('release_date'),
                    download_url=data.get('download_url'),
                    checksum=data.get('checksum'),
                    changelog=data.get('changelog'),
                    metadata=data.get('metadata', {}),
                )

            return None

        except (URLError, json.JSONDecodeError, ValueError, KeyError) as e:
            # Log error but don't fail the application
            logging.getLogger('teaagent.update').warning(f'Update check failed: {e}')
            return None


class UpdateChecker:
    """Checker for teaagent updates."""

    def __init__(
        self,
        current_version: str,
        channel: UpdateChannel = UpdateChannel.STABLE,
        server: Optional[UpdateServer] = None,
    ) -> None:
        """Initialize the update checker.

        Args:
            current_version: Current version string.
            channel: Update channel to check.
            server: Optional custom update server.
        """
        self.current_version = current_version
        self.channel = channel
        self.server = server or UpdateServer()

    def check_update(self) -> Optional[UpdateInfo]:
        """Check for available updates.

        Returns:
            UpdateInfo if update available, None otherwise.
        """
        return self.server.check_for_updates(self.current_version, self.channel)

    def get_current_version(self) -> Version:
        """Get current version.

        Returns:
            Current version.
        """
        return Version.from_string(self.current_version)

    def is_update_available(self) -> bool:
        """Check if an update is available.

        Returns:
            True if update available, False otherwise.
        """
        update_info = self.check_update()
        return update_info is not None

    def format_update_message(self, update_info: UpdateInfo) -> str:
        """Format a user-friendly update message.

        Args:
            update_info: Update information.

        Returns:
            Formatted message.
        """
        current = self.get_current_version()
        message = f'Update available: {current} → {update_info.version}'

        if update_info.changelog:
            message += f'\n\nChanges:\n{update_info.changelog}'

        if update_info.download_url:
            message += f'\n\nDownload: {update_info.download_url}'

        return message


def get_current_version() -> str:
    """Get the current teaagent version.

    Returns:
        Current version string.
    """
    # Try to read from package metadata
    try:
        from importlib.metadata import version

        return version('teaagent')
    except Exception:
        # Fallback to hardcoded version
        return '0.1.0'


def check_for_updates(
    channel: UpdateChannel = UpdateChannel.STABLE,
) -> Optional[UpdateInfo]:
    """Convenience function to check for updates.

    Args:
        channel: Update channel to check.

    Returns:
        UpdateInfo if update available, None otherwise.
    """
    current_version = get_current_version()
    checker = UpdateChecker(current_version, channel)
    return checker.check_update()
