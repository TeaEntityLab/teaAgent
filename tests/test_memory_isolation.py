"""Tests for branch-aware memory isolation (TASK-007)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from teaagent.memory import MemoryCatalog, MemoryEntry, memory_entry_from_payload


def test_memory_entry_with_branch_and_run_id() -> None:
    """Test MemoryEntry with branch_name and run_id fields."""
    entry = MemoryEntry(
        memory_id='test-id',
        content='Test content',
        tags=('test',),
        branch_name='teaagent-sandbox-123-optA',
        run_id='run-123',
    )
    assert entry.branch_name == 'teaagent-sandbox-123-optA'
    assert entry.run_id == 'run-123'

    entry_dict = entry.to_dict()
    assert entry_dict['branch_name'] == 'teaagent-sandbox-123-optA'
    assert entry_dict['run_id'] == 'run-123'


def test_memory_catalog_add_with_branch() -> None:
    """Test adding memory with branch_name."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        entry = catalog.add(
            'Test content',
            tags=('test',),
            branch_name='teaagent-sandbox-123-optA',
            run_id='run-123',
        )
        assert entry.branch_name == 'teaagent-sandbox-123-optA'
        assert entry.run_id == 'run-123'


def test_memory_catalog_delete_by_branch() -> None:
    """Test deleting memory entries by branch."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Content A', branch_name='branch-a')
        catalog.add('Content B', branch_name='branch-b')
        catalog.add('Content C', branch_name='branch-a')

        deleted = catalog.delete_by_branch('branch-a')
        assert deleted == 2

        entries = catalog.list()
        assert len(entries) == 1
        assert entries[0].branch_name == 'branch-b'


def test_memory_catalog_delete_by_run_id() -> None:
    """Test deleting memory entries by run_id."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Content A', run_id='run-1')
        catalog.add('Content B', run_id='run-2')
        catalog.add('Content C', run_id='run-1')

        deleted = catalog.delete_by_run_id('run-1')
        assert deleted == 2

        entries = catalog.list()
        assert len(entries) == 1
        assert entries[0].run_id == 'run-2'


def test_memory_catalog_quarantine_by_branch() -> None:
    """Test quarantining memory entries by branch."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Content A', branch_name='branch-a')
        catalog.add('Content B', branch_name='branch-b')
        catalog.add('Content C', branch_name='branch-a')

        quarantined = catalog.quarantine_by_branch('branch-a', 'Test quarantine')
        assert quarantined == 2

        # Check main catalog
        entries = catalog.list()
        assert len(entries) == 1
        assert entries[0].branch_name == 'branch-b'

        # Check quarantine file
        quarantine_path = Path(tmp) / '.teaagent' / 'memory-quarantine.jsonl'
        assert quarantine_path.exists()

        quarantine_entries = []
        for line in quarantine_path.read_text().splitlines():
            if line.strip():
                payload = json.loads(line)
                if payload.get('quarantine'):
                    quarantine_entries.append(payload)

        assert len(quarantine_entries) == 2
        for entry in quarantine_entries:
            assert entry['branch_name'] == 'branch-a'
            assert entry['provenance']['reason'] == 'Test quarantine'


def test_memory_entry_from_payload_with_branch() -> None:
    """Test memory_entry_from_payload with branch_name and run_id."""
    payload = {
        'memory_id': 'test-id',
        'content': 'Test content',
        'tags': ['test'],
        'created_at': '2024-01-01T00:00:00Z',
        'branch_name': 'branch-a',
        'run_id': 'run-123',
    }
    entry = memory_entry_from_payload(payload)
    assert entry is not None
    assert entry.branch_name == 'branch-a'
    assert entry.run_id == 'run-123'


def test_memory_entry_from_payload_without_branch() -> None:
    """Test memory_entry_from_payload without branch_name (backward compatibility)."""
    payload = {
        'memory_id': 'test-id',
        'content': 'Test content',
        'tags': ['test'],
        'created_at': '2024-01-01T00:00:00Z',
    }
    entry = memory_entry_from_payload(payload)
    assert entry is not None
    assert entry.branch_name is None
    assert entry.run_id is None


def test_memory_entry_from_payload_invalid_branch() -> None:
    """Test memory_entry_from_payload with invalid branch_name."""
    payload = {
        'memory_id': 'test-id',
        'content': 'Test content',
        'tags': ['test'],
        'created_at': '2024-01-01T00:00:00Z',
        'branch_name': 123,  # Invalid type
    }
    entry = memory_entry_from_payload(payload)
    assert entry is None


def test_memory_catalog_readonly_prevents_delete() -> None:
    """Test that readonly mode prevents deletion."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Test content', branch_name='branch-a')

        readonly_catalog = MemoryCatalog(tmp, readonly=True)
        with pytest.raises(RuntimeError):
            readonly_catalog.delete_by_branch('branch-a')


def test_memory_catalog_readonly_prevents_quarantine() -> None:
    """Test that readonly mode prevents quarantine."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Test content', branch_name='branch-a')

        readonly_catalog = MemoryCatalog(tmp, readonly=True)
        with pytest.raises(RuntimeError):
            readonly_catalog.quarantine_by_branch('branch-a', 'Test')


def test_memory_catalog_delete_nonexistent_branch() -> None:
    """Test deleting a branch that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add('Test content', branch_name='branch-a')

        deleted = catalog.delete_by_branch('nonexistent')
        assert deleted == 0

        entries = catalog.list()
        assert len(entries) == 1


def test_memory_catalog_quarantine_preserves_provenance() -> None:
    """Test that quarantine preserves original entry data."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        catalog.add(
            'Important content',
            tags=('important',),
            branch_name='branch-a',
            run_id='run-123',
        )

        catalog.quarantine_by_branch('branch-a', 'Test quarantine')

        quarantine_path = Path(tmp) / '.teaagent' / 'memory-quarantine.jsonl'
        quarantine_data = json.loads(quarantine_path.read_text().strip())

        assert quarantine_data['content'] == 'Important content'
        assert quarantine_data['tags'] == ['important']
        assert quarantine_data['branch_name'] == 'branch-a'
        assert quarantine_data['run_id'] == 'run-123'
        assert quarantine_data['quarantine']
        assert quarantine_data['provenance']['reason'] == 'Test quarantine'
        assert 'quarantined_at' in quarantine_data['provenance']
