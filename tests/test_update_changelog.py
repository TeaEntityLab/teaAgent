"""Tests for changelog display (TASK-H6-003-04)."""

from tempfile import TemporaryDirectory

import pytest

from teaagent.update.changelog import (
    ChangeEntry,
    Changelog,
    ChangelogEntry,
    ChangelogFormatter,
    ChangelogLoader,
    ChangeType,
)


@pytest.fixture
def loader():
    """Fixture for ChangelogLoader."""
    return ChangelogLoader()


@pytest.fixture
def formatter():
    """Fixture for ChangelogFormatter."""
    return ChangelogFormatter()


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    with TemporaryDirectory() as tmp:
        yield tmp


def test_to_dict_and_from_dict():
    """Test serialization."""
    entry = ChangeEntry(
        change_type=ChangeType.ADDED,
        description='New feature',
        component='core',
        issue_number='123',
    )

    data = entry.to_dict()
    restored = ChangeEntry.from_dict(data)

    assert restored.change_type == entry.change_type
    assert restored.description == entry.description


def test_changelog_entry_to_dict_and_from_dict():
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

    assert restored.version == entry.version
    assert len(restored.changes) == 1


def test_changelog_to_dict_and_from_dict():
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

    assert len(restored.entries) == 1


def test_add_entry():
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

    assert len(changelog.entries) == 1


def test_get_entry():
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

    assert retrieved.version == '1.2.3'


def test_get_entry_not_found():
    """Test getting non-existent entry."""
    changelog = Changelog()
    retrieved = changelog.get_entry('1.2.3')

    assert retrieved is None


def test_get_latest_entry():
    """Test getting latest entry."""
    changelog = Changelog()
    entry1 = ChangelogEntry(version='1.2.3')
    entry2 = ChangelogEntry(version='1.2.4')
    changelog.add_entry(entry1)
    changelog.add_entry(entry2)

    latest = changelog.get_latest_entry()

    assert latest.version == '1.2.3'


def test_get_latest_entry_empty():
    """Test getting latest entry from empty changelog."""
    changelog = Changelog()
    latest = changelog.get_latest_entry()

    assert latest is None


def test_get_entries_since():
    """Test getting entries since version."""
    changelog = Changelog()
    entry1 = ChangelogEntry(version='1.2.3')
    entry2 = ChangelogEntry(version='1.2.4')
    entry3 = ChangelogEntry(version='1.2.5')
    changelog.add_entry(entry1)
    changelog.add_entry(entry2)
    changelog.add_entry(entry3)

    entries = changelog.get_entries_since('1.2.3')

    assert len(entries) == 2


def test_format_entry(formatter):
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

    formatted = formatter.format_entry(entry)

    assert '1.2.3' in formatted
    assert 'New feature' in formatted
    assert 'Bug fix' in formatted


def test_format_summary(formatter):
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

    summary = formatter.format_summary(entry)

    assert '1.2.3' in summary
    assert 'Released' in summary


def test_format_diff(formatter):
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

    diff = formatter.format_diff('1.2.3', '1.2.5', changelog)

    assert '1.2.3' in diff
    assert '1.2.5' in diff


def test_format_diff_no_changes(formatter):
    """Test formatting diff with no changes."""
    changelog = Changelog()

    diff = formatter.format_diff('1.2.3', '1.2.4', changelog)

    assert 'No changes' in diff


def test_load_from_file_not_exists(loader):
    """Test loading from non-existent file."""
    changelog = loader.load_from_file('/nonexistent/file.json')

    assert len(changelog.entries) == 0


def test_save_and_load_from_file(loader, temp_dir):
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

    file_path = f'{temp_dir}/changelog.json'
    loader.save_to_file(changelog, file_path)

    loaded = loader.load_from_file(file_path)

    assert len(loaded.entries) == 1
    assert loaded.entries[0].version == '1.2.3'


def test_create_default_changelog(loader):
    """Test creating default changelog."""
    changelog = loader.create_default_changelog()

    assert len(changelog.entries) == 1
    assert changelog.entries[0].version == '0.1.0'
