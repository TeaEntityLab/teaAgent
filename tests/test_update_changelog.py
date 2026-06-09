"""Tests for changelog display (TASK-H6-003-04)."""

import unittest
from tempfile import TemporaryDirectory

from teaagent.update.changelog import (
    ChangeEntry,
    Changelog,
    ChangelogEntry,
    ChangelogFormatter,
    ChangelogLoader,
    ChangeType,
)


class TestChangeEntry(unittest.TestCase):
    """Test change entry."""

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        entry = ChangeEntry(
            change_type=ChangeType.ADDED,
            description='New feature',
            component='core',
            issue_number='123',
        )

        data = entry.to_dict()
        restored = ChangeEntry.from_dict(data)

        self.assertEqual(restored.change_type, entry.change_type)
        self.assertEqual(restored.description, entry.description)


class TestChangelogEntry(unittest.TestCase):
    """Test changelog entry."""

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        entry = ChangelogEntry(
            version='1.2.3',
            release_date='2024-01-01',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
            ],
        )

        data = entry.to_dict()
        restored = ChangelogEntry.from_dict(data)

        self.assertEqual(restored.version, entry.version)
        self.assertEqual(len(restored.changes), 1)


class TestChangelog(unittest.TestCase):
    """Test changelog."""

    def test_to_dict_and_from_dict(self):
        """Test serialization."""
        changelog = Changelog(
            entries=[
                ChangelogEntry(
                    version='1.2.3',
                    changes=[
                        ChangeEntry(
                            change_type=ChangeType.ADDED,
                            description='New feature',
                        ),
                    ],
                ),
            ],
        )

        data = changelog.to_dict()
        restored = Changelog.from_dict(data)

        self.assertEqual(len(restored.entries), 1)

    def test_add_entry(self):
        """Test adding changelog entry."""
        changelog = Changelog()
        entry = ChangelogEntry(
            version='1.2.3',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
            ],
        )

        changelog.add_entry(entry)

        self.assertEqual(len(changelog.entries), 1)

    def test_get_entry(self):
        """Test getting changelog entry."""
        changelog = Changelog()
        entry = ChangelogEntry(
            version='1.2.3',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
            ],
        )
        changelog.add_entry(entry)

        retrieved = changelog.get_entry('1.2.3')

        self.assertEqual(retrieved.version, '1.2.3')

    def test_get_entry_not_found(self):
        """Test getting non-existent entry."""
        changelog = Changelog()
        retrieved = changelog.get_entry('1.2.3')

        self.assertIsNone(retrieved)

    def test_get_latest_entry(self):
        """Test getting latest entry."""
        changelog = Changelog()
        entry1 = ChangelogEntry(version='1.2.3')
        entry2 = ChangelogEntry(version='1.2.4')
        changelog.add_entry(entry1)
        changelog.add_entry(entry2)

        latest = changelog.get_latest_entry()

        self.assertEqual(latest.version, '1.2.3')

    def test_get_latest_entry_empty(self):
        """Test getting latest entry from empty changelog."""
        changelog = Changelog()
        latest = changelog.get_latest_entry()

        self.assertIsNone(latest)

    def test_get_entries_since(self):
        """Test getting entries since version."""
        changelog = Changelog()
        entry1 = ChangelogEntry(version='1.2.3')
        entry2 = ChangelogEntry(version='1.2.4')
        entry3 = ChangelogEntry(version='1.2.5')
        changelog.add_entry(entry1)
        changelog.add_entry(entry2)
        changelog.add_entry(entry3)

        entries = changelog.get_entries_since('1.2.3')

        self.assertEqual(len(entries), 2)


class TestChangelogFormatter(unittest.TestCase):
    """Test changelog formatter."""

    def setUp(self):
        """Set up test fixtures."""
        self.formatter = ChangelogFormatter()

    def test_format_entry(self):
        """Test formatting changelog entry."""
        entry = ChangelogEntry(
            version='1.2.3',
            release_date='2024-01-01',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                    component='core',
                ),
                ChangeEntry(
                    change_type=ChangeType.FIXED,
                    description='Bug fix',
                ),
            ],
        )

        formatted = self.formatter.format_entry(entry)

        self.assertIn('1.2.3', formatted)
        self.assertIn('New feature', formatted)
        self.assertIn('Bug fix', formatted)

    def test_format_summary(self):
        """Test formatting changelog summary."""
        entry = ChangelogEntry(
            version='1.2.3',
            release_date='2024-01-01',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
                ChangeEntry(
                    change_type=ChangeType.FIXED,
                    description='Bug fix',
                ),
            ],
        )

        summary = self.formatter.format_summary(entry)

        self.assertIn('1.2.3', summary)
        self.assertIn('Released', summary)

    def test_format_diff(self):
        """Test formatting diff between versions."""
        changelog = Changelog()
        entry1 = ChangelogEntry(
            version='1.2.4',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
            ],
        )
        entry2 = ChangelogEntry(
            version='1.2.5',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.FIXED,
                    description='Bug fix',
                ),
            ],
        )
        changelog.add_entry(entry1)
        changelog.add_entry(entry2)

        diff = self.formatter.format_diff('1.2.3', '1.2.5', changelog)

        self.assertIn('1.2.3', diff)
        self.assertIn('1.2.5', diff)

    def test_format_diff_no_changes(self):
        """Test formatting diff with no changes."""
        changelog = Changelog()

        diff = self.formatter.format_diff('1.2.3', '1.2.4', changelog)

        self.assertIn('No changes', diff)


class TestChangelogLoader(unittest.TestCase):
    """Test changelog loader."""

    def setUp(self):
        """Set up test fixtures."""
        self.loader = ChangelogLoader()
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_load_from_file_not_exists(self):
        """Test loading from non-existent file."""
        changelog = self.loader.load_from_file('/nonexistent/file.json')

        self.assertEqual(len(changelog.entries), 0)

    def test_save_and_load_from_file(self):
        """Test saving and loading from file."""
        changelog = Changelog()
        entry = ChangelogEntry(
            version='1.2.3',
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='New feature',
                ),
            ],
        )
        changelog.add_entry(entry)

        file_path = f'{self.temp_dir.name}/changelog.json'
        self.loader.save_to_file(changelog, file_path)

        loaded = self.loader.load_from_file(file_path)

        self.assertEqual(len(loaded.entries), 1)
        self.assertEqual(loaded.entries[0].version, '1.2.3')

    def test_create_default_changelog(self):
        """Test creating default changelog."""
        changelog = self.loader.create_default_changelog()

        self.assertEqual(len(changelog.entries), 1)
        self.assertEqual(changelog.entries[0].version, '0.1.0')


if __name__ == '__main__':
    unittest.main()
