"""Changelog display for update UI (TASK-H6-003-04).

This module provides changelog formatting, display, and version history
for the update mechanism.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .update import Version


class ChangeType(str, Enum):
    """Type of change in changelog."""

    ADDED = 'added'  # New features
    CHANGED = 'changed'  # Changes to existing features
    DEPRECATED = 'deprecated'  # Deprecated features
    REMOVED = 'removed'  # Removed features
    FIXED = 'fixed'  # Bug fixes
    SECURITY = 'security'  # Security fixes


@dataclass
class ChangeEntry:
    """A single change entry in the changelog."""

    change_type: ChangeType
    description: str
    component: Optional[str] = None
    issue_number: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'change_type': self.change_type.value,
            'description': self.description,
            'component': self.component,
            'issue_number': self.issue_number,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ChangeEntry':
        """Create from dictionary."""
        return cls(
            change_type=ChangeType(data['change_type']),
            description=data['description'],
            component=data.get('component'),
            issue_number=data.get('issue_number'),
            metadata=data.get('metadata', {}),
        )


@dataclass
class ChangelogEntry:
    """A changelog entry for a specific version."""

    version: str
    release_date: Optional[str] = None
    changes: list[ChangeEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'release_date': self.release_date,
            'changes': [change.to_dict() for change in self.changes],
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ChangelogEntry':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            release_date=data.get('release_date'),
            changes=[ChangeEntry.from_dict(c) for c in data.get('changes', [])],
            metadata=data.get('metadata', {}),
        )


@dataclass
class Changelog:
    """A complete changelog with version history."""

    entries: list[ChangelogEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entries': [entry.to_dict() for entry in self.entries],
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Changelog':
        """Create from dictionary."""
        return cls(
            entries=[ChangelogEntry.from_dict(e) for e in data.get('entries', [])],
            metadata=data.get('metadata', {}),
        )

    def add_entry(self, entry: ChangelogEntry) -> None:
        """Add a changelog entry.

        Args:
            entry: Changelog entry to add.
        """
        self.entries.append(entry)

    def get_entry(self, version: str) -> Optional[ChangelogEntry]:
        """Get changelog entry for a specific version.

        Args:
            version: Version string.

        Returns:
            Changelog entry if found, None otherwise.
        """
        for entry in self.entries:
            if entry.version == version:
                return entry
        return None

    def get_latest_entry(self) -> Optional[ChangelogEntry]:
        """Get the latest changelog entry.

        Returns:
            Latest changelog entry if available, None otherwise.
        """
        if not self.entries:
            return None
        return self.entries[0]

    def get_entries_since(self, version: str) -> list[ChangelogEntry]:
        """Get changelog entries since a specific version.

        Args:
            version: Version string.

        Returns:
            List of changelog entries since the version.
        """
        entries = []
        for entry in self.entries:
            try:
                entry_version = Version.from_string(entry.version)
                since_version = Version.from_string(version)
                if entry_version > since_version:
                    entries.append(entry)
            except ValueError:
                # Skip if version parsing fails
                continue
        return entries


class ChangelogFormatter:
    """Formatter for changelog display."""

    def __init__(self) -> None:
        """Initialize the changelog formatter."""
        self.change_type_icons = {
            ChangeType.ADDED: '✨',
            ChangeType.CHANGED: '🔄',
            ChangeType.DEPRECATED: '⚠️',
            ChangeType.REMOVED: '🗑️',
            ChangeType.FIXED: '🐛',
            ChangeType.SECURITY: '🔒',
        }

    def format_entry(self, entry: ChangelogEntry) -> str:
        """Format a changelog entry for display.

        Args:
            entry: Changelog entry to format.

        Returns:
            Formatted string.
        """
        lines = []
        lines.append(f'## {entry.version}')

        if entry.release_date:
            lines.append(f'Released: {entry.release_date}')

        lines.append('')

        # Group changes by type
        changes_by_type: dict[ChangeType, list[ChangeEntry]] = {}
        for change in entry.changes:
            if change.change_type not in changes_by_type:
                changes_by_type[change.change_type] = []
            changes_by_type[change.change_type].append(change)

        # Format each type
        for change_type in [
            ChangeType.ADDED,
            ChangeType.CHANGED,
            ChangeType.DEPRECATED,
            ChangeType.REMOVED,
            ChangeType.FIXED,
            ChangeType.SECURITY,
        ]:
            if change_type not in changes_by_type:
                continue

            icon = self.change_type_icons.get(change_type, '')
            lines.append(f'### {icon} {change_type.value.capitalize()}')

            for change in changes_by_type[change_type]:
                line = f'- {change.description}'
                if change.component:
                    line += f' ({change.component})'
                if change.issue_number:
                    line += f' [#{change.issue_number}]'
                lines.append(line)

            lines.append('')

        return '\n'.join(lines)

    def format_summary(self, entry: ChangelogEntry) -> str:
        """Format a summary of a changelog entry.

        Args:
            entry: Changelog entry to format.

        Returns:
            Formatted summary string.
        """
        lines = []
        lines.append(f'Version {entry.version}')

        if entry.release_date:
            lines.append(f'Released: {entry.release_date}')

        # Count changes by type
        change_counts: dict[ChangeType, int] = {}
        for change in entry.changes:
            change_counts[change.change_type] = (
                change_counts.get(change.change_type, 0) + 1
            )

        # Format counts
        summary_parts = []
        for change_type in [
            ChangeType.ADDED,
            ChangeType.CHANGED,
            ChangeType.FIXED,
            ChangeType.SECURITY,
        ]:
            if change_type in change_counts:
                count = change_counts[change_type]
                icon = self.change_type_icons.get(change_type, '')
                summary_parts.append(f'{icon} {count} {change_type.value}')

        if summary_parts:
            lines.append(' | '.join(summary_parts))

        return '\n'.join(lines)

    def format_diff(
        self,
        from_version: str,
        to_version: str,
        changelog: Changelog,
    ) -> str:
        """Format a diff between two versions.

        Args:
            from_version: Starting version.
            to_version: Target version.
            changelog: Changelog to format.

        Returns:
            Formatted diff string.
        """
        entries = changelog.get_entries_since(from_version)

        if not entries:
            return f'No changes between {from_version} and {to_version}'

        lines = []
        lines.append(f'Changes from {from_version} to {to_version}:')
        lines.append('')

        for entry in entries:
            lines.append(self.format_entry(entry))

        return '\n'.join(lines)


class ChangelogLoader:
    """Loader for changelog data."""

    def __init__(self) -> None:
        """Initialize the changelog loader."""
        pass

    def load_from_file(self, file_path: str) -> Changelog:
        """Load changelog from file.

        Args:
            file_path: Path to changelog file.

        Returns:
            Changelog object.
        """
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return Changelog()

        data = json.loads(path.read_text(encoding='utf-8'))
        return Changelog.from_dict(data)

    def save_to_file(self, changelog: Changelog, file_path: str) -> None:
        """Save changelog to file.

        Args:
            changelog: Changelog to save.
            file_path: Path to save changelog to.
        """
        from pathlib import Path

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            json.dumps(changelog.to_dict(), indent=2),
            encoding='utf-8',
        )

    def create_default_changelog(self) -> Changelog:
        """Create a default changelog.

        Returns:
            Default changelog.
        """
        changelog = Changelog()

        # Add initial entry
        entry = ChangelogEntry(
            version='0.1.0',
            release_date=datetime.now().isoformat(),
            changes=[
                ChangeEntry(
                    change_type=ChangeType.ADDED,
                    description='Initial release of teaagent',
                    component='core',
                ),
            ],
        )
        changelog.add_entry(entry)

        return changelog
