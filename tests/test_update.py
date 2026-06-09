"""Tests for update check mechanism (TASK-H6-003-01)."""

import json
import unittest
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


class TestVersion(unittest.TestCase):
    """Test version parsing and comparison."""

    def test_version_from_string(self):
        """Test parsing version from string."""
        version = Version.from_string('1.2.3')
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 2)
        self.assertEqual(version.patch, 3)

    def test_from_string_with_prerelease(self):
        """Test parsing version with prerelease."""
        version = Version.from_string('1.2.3-beta')
        self.assertEqual(version.prerelease, 'beta')

    def test_from_string_with_build(self):
        """Test parsing version with build."""
        version = Version.from_string('1.2.3+build123')
        self.assertEqual(version.build, 'build123')

    def test_version_comparison(self):
        """Test version comparison."""
        v1 = Version.from_string('1.2.3')
        v2 = Version.from_string('1.2.4')
        self.assertTrue(v1 < v2)
        self.assertFalse(v2 < v1)

    def test_version_equality(self):
        """Test version equality."""
        v1 = Version.from_string('1.2.3')
        v2 = Version.from_string('1.2.3')
        self.assertEqual(v1, v2)

    def test_version_str(self):
        """Test version string representation."""
        version = Version.from_string('1.2.3-beta')
        self.assertEqual(str(version), '1.2.3-beta')

    def test_prerelease_comparison(self):
        """Test prerelease version comparison."""
        v1 = Version.from_string('1.2.3')
        v2 = Version.from_string('1.2.3-beta')
        self.assertTrue(v2 < v1)  # Prerelease < stable
        self.assertFalse(v1 < v2)


class TestUpdateInfo(unittest.TestCase):
    """Test update information."""

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        info = UpdateInfo(
            version=Version.from_string('1.2.3'),
            channel=UpdateChannel.STABLE,
            release_date='2024-01-01',
            download_url='https://example.com/download',
        )

        data = info.to_dict()
        restored = UpdateInfo.from_dict(data)

        self.assertEqual(restored.version, info.version)
        self.assertEqual(restored.channel, info.channel)
        self.assertEqual(restored.download_url, info.download_url)


class TestUpdateServer(unittest.TestCase):
    """Test update server communication."""

    def test_init(self):
        """Test update server initialization."""
        server = UpdateServer('https://api.example.com')
        self.assertEqual(server.base_url, 'https://api.example.com')

    def test_init_trailing_slash(self):
        """Test update server initialization with trailing slash."""
        server = UpdateServer('https://api.example.com/')
        self.assertEqual(server.base_url, 'https://api.example.com')

    @patch('teaagent.update.update.urlopen')
    def test_check_for_updates_available(self, mock_urlopen):
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
        mock_urlopen.return_value.__enter__.return_value = mock_response

        server = UpdateServer('https://api.example.com')
        update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

        self.assertIsNotNone(update_info)
        self.assertEqual(str(update_info.version), '1.2.4')

    @patch('teaagent.update.update.urlopen')
    def test_check_for_updates_none(self, mock_urlopen):
        """Test checking for updates when no update available."""
        # Mock response with same version
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(
            {
                'version': '1.2.3',
            }
        ).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        server = UpdateServer('https://api.example.com')
        update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

        self.assertIsNone(update_info)

    @patch('teaagent.update.update.urlopen')
    def test_check_for_updates_error(self, mock_urlopen):
        """Test checking for updates on error."""
        # Mock error
        mock_urlopen.side_effect = URLError('Network error')

        server = UpdateServer('https://api.example.com')
        update_info = server.check_for_updates('1.2.3', UpdateChannel.STABLE)

        self.assertIsNone(update_info)


class TestUpdateChecker(unittest.TestCase):
    """Test update checker."""

    def test_init(self):
        """Test update checker initialization."""
        checker = UpdateChecker('1.2.3')
        self.assertEqual(checker.current_version, '1.2.3')
        self.assertEqual(checker.channel, UpdateChannel.STABLE)

    def test_init_with_channel(self):
        """Test update checker initialization with channel."""
        checker = UpdateChecker('1.2.3', channel=UpdateChannel.BETA)
        self.assertEqual(checker.channel, UpdateChannel.BETA)

    def test_get_current_version(self):
        """Test getting current version."""
        checker = UpdateChecker('1.2.3')
        version = checker.get_current_version()
        self.assertEqual(str(version), '1.2.3')

    @patch('teaagent.update.update.UpdateServer')
    def test_check_update(self, mock_server):
        """Test checking for update."""
        mock_update_info = UpdateInfo(
            version=Version.from_string('1.2.4'),
            channel=UpdateChannel.STABLE,
        )
        mock_server.check_for_updates.return_value = mock_update_info

        checker = UpdateChecker('1.2.3', server=mock_server)
        update_info = checker.check_update()

        self.assertEqual(update_info, mock_update_info)

    @patch('teaagent.update.update.UpdateServer')
    def test_is_update_available_true(self, mock_server):
        """Test checking if update is available (true)."""
        mock_update_info = UpdateInfo(
            version=Version.from_string('1.2.4'),
            channel=UpdateChannel.STABLE,
        )
        mock_server.check_for_updates.return_value = mock_update_info

        checker = UpdateChecker('1.2.3', server=mock_server)
        self.assertTrue(checker.is_update_available())

    @patch('teaagent.update.update.UpdateServer')
    def test_is_update_available_false(self, mock_server):
        """Test checking if update is available (false)."""
        mock_server.check_for_updates.return_value = None

        checker = UpdateChecker('1.2.3', server=mock_server)
        self.assertFalse(checker.is_update_available())

    def test_format_update_message(self):
        """Test formatting update message."""
        update_info = UpdateInfo(
            version=Version.from_string('1.2.4'),
            channel=UpdateChannel.STABLE,
            changelog='Bug fixes and improvements',
            download_url='https://example.com/download',
        )

        checker = UpdateChecker('1.2.3')
        message = checker.format_update_message(update_info)

        self.assertIn('1.2.3', message)
        self.assertIn('1.2.4', message)
        self.assertIn('Bug fixes and improvements', message)
        self.assertIn('https://example.com/download', message)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    @patch('importlib.metadata.version')
    def test_get_current_version(self, mock_version):
        """Test getting current version."""
        mock_version.return_value = '1.2.3'
        version = get_current_version()
        self.assertEqual(version, '1.2.3')

    @patch('teaagent.update.update.UpdateChecker')
    @patch('teaagent.update.update.get_current_version')
    def test_check_for_updates(self, mock_get_version, mock_checker):
        """Test convenience function for checking updates."""
        mock_get_version.return_value = '1.2.3'
        mock_update_info = UpdateInfo(
            version=Version.from_string('1.2.4'),
            channel=UpdateChannel.STABLE,
        )
        mock_checker.return_value.check_update.return_value = mock_update_info

        update_info = check_for_updates(UpdateChannel.STABLE)

        self.assertEqual(update_info, mock_update_info)


if __name__ == '__main__':
    unittest.main()
