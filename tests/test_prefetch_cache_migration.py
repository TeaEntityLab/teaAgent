"""Tests for prefetch_cache migration."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from teaagent.graphqlite_production import _GRAPHQLITE_SCHEMA_MIGRATIONS
from teaagent.schema_migration import (
    MigrationRunner,
    SQLiteMigrationStore,
)


def test_prefetch_cache_migration_creates_table() -> None:
    """Test that version 6 migration creates prefetch_cache table."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / 'test.db'
        store = SQLiteMigrationStore(db_path)
        conn = sqlite3.connect(str(db_path))

        # Find version 6 migration
        migration = next(
            (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
        )
        assert migration is not None, 'Version 6 migration should exist'

        # Apply migration
        runner = MigrationRunner(store, [migration], target_conn=conn)
        result = runner.apply_pending()

        assert result.ok
        assert 6 in result.applied

        # Verify table exists
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        assert 'prefetch_cache' in tables

        # Verify indexes exist
        indexes = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        ]
        assert 'idx_prefetch_created_at' in indexes
        assert 'idx_prefetch_source' in indexes

        conn.close()


def test_prefetch_cache_table_schema() -> None:
    """Test that prefetch_cache table has correct schema."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / 'test.db'
        store = SQLiteMigrationStore(db_path)
        conn = sqlite3.connect(str(db_path))

        migration = next(
            (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
        )
        assert migration is not None

        runner = MigrationRunner(store, [migration], target_conn=conn)
        runner.apply_pending()

        # Verify schema
        schema = conn.execute('PRAGMA table_info(prefetch_cache)').fetchall()
        columns = {row[1]: row[2] for row in schema}

        assert 'doc_id' in columns
        assert 'text' in columns
        assert 'source' in columns
        assert 'created_at' in columns
        assert 'metadata' in columns

        conn.close()


def test_prefetch_cache_migration_idempotent() -> None:
    """Test that migration can be applied multiple times safely."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / 'test.db'
        store = SQLiteMigrationStore(db_path)
        conn = sqlite3.connect(str(db_path))

        migration = next(
            (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
        )
        assert migration is not None

        # Apply twice
        runner1 = MigrationRunner(store, [migration], target_conn=conn)
        result1 = runner1.apply_pending()
        assert 6 in result1.applied

        runner2 = MigrationRunner(store, [migration], target_conn=conn)
        result2 = runner2.apply_pending()
        assert result2.applied == []

        conn.close()
