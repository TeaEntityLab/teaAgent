"""Tests for update check mechanism (TASK-H6-003-01)."""

import json
from unittest.mock import Mock, patch
from urllib.error import URLError

from teaagent.update.update import (
    UpdateChannel,
    UpdateChecker,
    UpdateInfo,
    UpdateServer,
    Version,
    check_for_updates,
    get_current_version,
)


def test_version_from_string():
    """Test parsing version from string."""
    version = Version.from_string('1.2.3')
    assert version.major == 1
    assert version.minor == 2
    assert version.patch == 3


def test_from_string_with_prerelease():
    """Test parsing version with prerelease."""
    version = Version.from_string('1.2.3-beta')
    assert version.prerelease == 'beta'


def test_from_string_with_build():
    """Test parsing version with build."""
    version = Version.from_string('1.2.3+build123')
    assert version.build == 'build123'


def test_version_comparison():
    """Test version comparison."""
    v1 = Version.from_string('1.2.3')
    v2 = Version.from_string('1.2.4')
    assert v1 < v2
    assert not (v2 < v1)


def test_version_equality():
    """Test version equality."""
    v1 = Version.from_string('1.2.3')
    v2 = Version.from_string('1.2.3')
    assert v1 == v2


def test_version_str():
    """Test version string representation."""
    version = Version.from_string('1.2.3-beta')
    assert str(version) == '1.2.3-beta'


def test_prerelease_comparison():
    """Test prerelease version comparison."""
    v1 = Version.from_string('1.2.3')
    v2 = Version.from_string('1.2.3-beta')
    assert v2 < v1  # Prerelease < stable
    assert not (v1 < v2)


def test_update_info_to_dict_and_from_dict():
    """Test serialization."""
    info = UpdateInfo(
        version=Version.from_string('1.2.3'),
        channel=UpdateChannel.STABLE,
        release_date='2024-01-01',
        download_url='https://example.com/download',
    )

    data = info.to_dict()
    restored = UpdateInfo.from_dict(data)

    assert restored.version == info.version
    assert restored.channel == info.channel
    assert restored.download_url == info.download_url


def test_update_server_init():
    """Test update server initialization."""
    server = UpdateServer('https://api.example.com')
    assert server.base_url == 'https://api.example.com'


def test_update_server_init_trailing_slash():
    """Test update server initialization with trailing slash."""
    server = UpdateServer('https://api.example.com/')
    assert server.base_url == 'https://api.example.com'


@patch('teaagent.update.update.safe_urlopen')
def test_check_for_updates_available(mock_safe_urlopen):
    """Test checking for updates when update available."""
    # Mock response
    mock_response = Mock()
    mock_response.read.return_value = json.dumps(
        {
            'version': '1.2.4',
            'release_date': '2024-01-01',
            'download_url': 'https://example.com/download',
            'changelog': 'Bug fixes and improvements',
        }
    ).encode('utf-8')
    mock_safe_urlopen.return_value.__enter__.return_value = mock_response

    server = UpdateServer('https://api.example.com')
    update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

    assert update_info is not None
    assert str(update_info.version) == '1.2.4'


@patch('teaagent.update.update.safe_urlopen')
def test_check_for_updates_none(mock_safe_urlopen):
    """Test checking for updates when no update available."""
    # Mock response with same version
    mock_response = Mock()
    mock_response.read.return_value = json.dumps(
        {
            'version': '1.2.3',
        }
    ).encode('utf-8')
    mock_safe_urlopen.return_value.__enter__.return_value = mock_response

    server = UpdateServer('https://api.example.com')
    update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

    assert update_info is None


@patch('teaagent.update.update.safe_urlopen')
def test_check_for_updates_error(mock_safe_urlopen):
    """Test checking for updates on error."""
    # Mock error
    mock_safe_urlopen.side_effect = URLError('Network error')

    server = UpdateServer('https://api.example.com')
    update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

    assert update_info is None


def test_update_checker_init():
    """Test update checker initialization."""
    checker = UpdateChecker('1.2.3')
    assert checker.current_version == '1.2.3'
    assert checker.channel == UpdateChannel.STABLE


def test_update_checker_init_with_channel():
    """Test update checker initialization with channel."""
    checker = UpdateChecker('1.2.3', channel=UpdateChannel.BETA)
    assert checker.channel == UpdateChannel.BETA


def test_update_checker_get_current_version():
    """Test getting current version."""
    checker = UpdateChecker('1.2.3')
    version = checker.get_current_version()
    assert str(version) == '1.2.3'


@patch('teaagent.update.update.UpdateServer')
def test_update_checker_check_update(mock_server):
    """Test checking for update."""
    mock_update_info = UpdateInfo(
        version=Version.from_string('1.2.4'),
        channel=UpdateChannel.STABLE,
    )
    mock_server.check_for_updates.return_value = mock_update_info

    checker = UpdateChecker('1.2.3', server=mock_server)
    update_info = checker.check_update()

    assert update_info == mock_update_info


@patch('teaagent.update.update.UpdateServer')
def test_update_checker_is_update_available_true(mock_server):
    """Test checking if update is available (true)."""
    mock_update_info = UpdateInfo(
        version=Version.from_string('1.2.4'),
        channel=UpdateChannel.STABLE,
    )
    mock_server.check_for_updates.return_value = mock_update_info

    checker = UpdateChecker('1.2.3', server=mock_server)
    assert checker.is_update_available() is True


@patch('teaagent.update.update.UpdateServer')
def test_update_checker_is_update_available_false(mock_server):
    """Test checking if update is available (false)."""
    mock_server.check_for_updates.return_value = None

    checker = UpdateChecker('1.2.3', server=mock_server)
    assert checker.is_update_available() is False


def test_update_checker_format_update_message():
    """Test formatting update message."""
    update_info = UpdateInfo(
        version=Version.from_string('1.2.4'),
        channel=UpdateChannel.STABLE,
        changelog='Bug fixes and improvements',
        download_url='https://example.com/download',
    )

    checker = UpdateChecker('1.2.3')
    message = checker.format_update_message(update_info)

    assert '1.2.3' in message
    assert '1.2.4' in message
    assert 'Bug fixes and improvements' in message
    assert 'https://example.com/download' in message


@patch('importlib.metadata.version')
def test_get_current_version(mock_version):
    """Test getting current version."""
    mock_version.return_value = '1.2.3'
    version = get_current_version()
    assert version == '1.2.3'


@patch('teaagent.update.update.UpdateChecker')
@patch('teaagent.update.update.get_current_version')
def test_check_for_updates(mock_get_version, mock_checker):
    """Test convenience function for checking updates."""
    mock_get_version.return_value = '1.2.3'
    mock_update_info = UpdateInfo(
        version=Version.from_string('1.2.4'),
        channel=UpdateChannel.STABLE,
    )
    mock_checker.return_value.check_update.return_value = mock_update_info

    update_info = check_for_updates(UpdateChannel.STABLE)

    assert update_info == mock_update_info
