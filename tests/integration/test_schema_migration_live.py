"""IT-14: Schema migration framework handles live non-empty databases.

Verifies that:
- Migration runner applies all pending migrations in order.
- Existing data survives migration.
- Running migrations twice is idempotent (already-applied migrations skipped).
- Version tracking prevents double-application.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from teaagent.schema_migration import (
    MigrationRunner,
    SchemaMigration,
    SQLiteMigrationStore,
)


def _make_migrations() -> list[SchemaMigration]:
    return [
        SchemaMigration(
            version=1,
            description='Create items table',
            sql='CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);',
        ),
        SchemaMigration(
            version=2,
            description='Add created_at column',
            sql='ALTER TABLE items ADD COLUMN created_at TEXT;',
        ),
        SchemaMigration(
            version=3,
            description='Create index on name',
            sql='CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);',
        ),
    ]


def _make_runner(
    db_path: Path, migrations: list[SchemaMigration]
) -> tuple[MigrationRunner, sqlite3.Connection]:
    """Return a runner + shared connection to the same DB file."""
    conn = sqlite3.connect(str(db_path))
    store = SQLiteMigrationStore(db_path)
    runner = MigrationRunner(store, migrations=migrations, target_conn=conn)
    return runner, conn


def test_migration_runner_applies_all_versions(tmp_path):
    db_path = tmp_path / 'test.db'
    migrations = _make_migrations()
    runner, conn = _make_runner(db_path, migrations)
    try:
        result = runner.apply_pending()
        assert result.ok  # bool field

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
        )
        assert cursor.fetchone() is not None, 'items table must exist after migration'
    finally:
        conn.close()


def test_migration_idempotent(tmp_path):
    db_path = tmp_path / 'test.db'
    migrations = _make_migrations()
    runner, conn = _make_runner(db_path, migrations)
    try:
        runner.apply_pending()
        result2 = runner.apply_pending()  # second run must not raise or double-apply
        assert result2.ok  # bool field

        store = SQLiteMigrationStore(db_path)
        applied = store.applied_versions()
        assert sorted(applied) == [1, 2, 3]
    finally:
        conn.close()


def test_existing_data_survives_migration(tmp_path):
    db_path = tmp_path / 'test.db'
    migrations = _make_migrations()

    # Bootstrap v1 schema + seed data manually
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        'CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL);'
    )
    conn.execute("INSERT INTO items (name) VALUES ('legacy-item')")
    conn.commit()

    # Mark v1 as already applied so runner skips it
    store = SQLiteMigrationStore(db_path)
    store.mark_applied(migrations[0])

    runner = MigrationRunner(store, migrations=migrations, target_conn=conn)
    result = runner.apply_pending()
    assert result.ok  # bool field

    row = conn.execute("SELECT name FROM items WHERE name='legacy-item'").fetchone()
    assert row is not None, 'legacy data must survive migration'
    conn.close()


def test_version_tracking_prevents_double_apply(tmp_path):
    db_path = tmp_path / 'test.db'
    migrations = _make_migrations()
    runner, conn = _make_runner(db_path, migrations)
    try:
        runner.apply_pending()

        store = SQLiteMigrationStore(db_path)
        applied_before = set(store.applied_versions())
        runner.apply_pending()  # should be no-op
        applied_after = set(store.applied_versions())
        assert applied_before == applied_after
    finally:
        conn.close()
