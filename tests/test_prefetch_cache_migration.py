"""Tests for prefetch_cache migration."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from teaagent.graphqlite_production import _GRAPHQLITE_SCHEMA_MIGRATIONS
from teaagent.schema_migration import (
    MigrationRunner,
    SQLiteMigrationStore,
)


class PrefetchCacheMigrationTests(unittest.TestCase):
    def test_prefetch_cache_migration_creates_table(self) -> None:
        """Test that version 6 migration creates prefetch_cache table."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'test.db'
            store = SQLiteMigrationStore(db_path)
            conn = sqlite3.connect(str(db_path))

            # Find version 6 migration
            migration = next(
                (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
            )
            self.assertIsNotNone(migration, 'Version 6 migration should exist')

            # Apply migration
            runner = MigrationRunner(store, [migration], target_conn=conn)
            result = runner.apply_pending()

            self.assertTrue(result.ok)
            self.assertIn(6, result.applied)

            # Verify table exists
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ]
            self.assertIn('prefetch_cache', tables)

            # Verify indexes exist
            indexes = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            ]
            self.assertIn('idx_prefetch_created_at', indexes)
            self.assertIn('idx_prefetch_source', indexes)

            conn.close()

    def test_prefetch_cache_table_schema(self) -> None:
        """Test that prefetch_cache table has correct schema."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'test.db'
            store = SQLiteMigrationStore(db_path)
            conn = sqlite3.connect(str(db_path))

            migration = next(
                (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
            )
            self.assertIsNotNone(migration)

            runner = MigrationRunner(store, [migration], target_conn=conn)
            runner.apply_pending()

            # Verify schema
            schema = conn.execute('PRAGMA table_info(prefetch_cache)').fetchall()
            columns = {row[1]: row[2] for row in schema}

            self.assertIn('doc_id', columns)
            self.assertIn('text', columns)
            self.assertIn('source', columns)
            self.assertIn('created_at', columns)
            self.assertIn('metadata', columns)

            conn.close()

    def test_prefetch_cache_migration_idempotent(self) -> None:
        """Test that migration can be applied multiple times safely."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'test.db'
            store = SQLiteMigrationStore(db_path)
            conn = sqlite3.connect(str(db_path))

            migration = next(
                (m for m in _GRAPHQLITE_SCHEMA_MIGRATIONS if m.version == 6), None
            )
            self.assertIsNotNone(migration)

            # Apply twice
            runner1 = MigrationRunner(store, [migration], target_conn=conn)
            result1 = runner1.apply_pending()
            self.assertIn(6, result1.applied)

            runner2 = MigrationRunner(store, [migration], target_conn=conn)
            result2 = runner2.apply_pending()
            self.assertEqual(result2.applied, [])

            conn.close()


if __name__ == '__main__':
    unittest.main()
