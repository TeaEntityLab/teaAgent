"""IT: MigrationRunner dry-run mode.

dry_run=True previews which migrations would run without executing any SQL or
marking anything as applied.
"""

from __future__ import annotations

import sqlite3

from teaagent.schema_migration import (
    MigrationResult,
    MigrationRunner,
    SchemaMigration,
    SQLiteMigrationStore,
)


def _migrations() -> list[SchemaMigration]:
    return [
        SchemaMigration(
            version=1,
            description='Create items',
            sql='CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY);',
        ),
        SchemaMigration(
            version=2,
            description='Add name column',
            sql='ALTER TABLE items ADD COLUMN name TEXT;',
        ),
        SchemaMigration(
            version=3,
            description='Create index',
            sql='CREATE INDEX IF NOT EXISTS idx_name ON items(name);',
        ),
    ]


def test_dry_run_does_not_create_table(tmp_path):
    db = tmp_path / 'app.db'
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    target = sqlite3.connect(str(db))
    runner = MigrationRunner(store, migrations=_migrations(), target_conn=target)

    result = runner.apply_pending(dry_run=True)

    assert result.ok
    # Table must NOT exist — dry run must not execute SQL
    cur = target.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
    )
    assert cur.fetchone() is None, 'dry_run must not create table'


def test_dry_run_returns_pending_versions(tmp_path):
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    runner = MigrationRunner(store, migrations=_migrations())

    result = runner.apply_pending(dry_run=True)

    assert set(result.dry_run_pending) == {1, 2, 3}
    assert result.applied == []
    assert result.total_pending == 3


def test_dry_run_after_partial_apply(tmp_path):
    db = tmp_path / 'app.db'
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    target = sqlite3.connect(str(db))
    runner = MigrationRunner(store, migrations=_migrations(), target_conn=target)

    # Apply v1 for real
    store.mark_applied(_migrations()[0])

    result = runner.apply_pending(dry_run=True)

    assert set(result.dry_run_pending) == {2, 3}
    assert result.total_pending == 2


def test_dry_run_does_not_mark_applied(tmp_path):
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    runner = MigrationRunner(store, migrations=_migrations())

    runner.apply_pending(dry_run=True)

    # After dry run, applied_versions must still be empty
    assert store.applied_versions() == []


def test_normal_run_after_dry_run_applies_all(tmp_path):
    db = tmp_path / 'app.db'
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    target = sqlite3.connect(str(db))
    runner = MigrationRunner(store, migrations=_migrations(), target_conn=target)

    runner.apply_pending(dry_run=True)  # preview
    result = runner.apply_pending()  # apply for real

    assert result.ok
    assert set(result.applied) == {1, 2, 3}
    cur = target.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
    )
    assert cur.fetchone() is not None, 'table must exist after normal apply'


def test_dry_run_all_applied_returns_empty_pending(tmp_path):
    store = SQLiteMigrationStore(tmp_path / 'migration.db')
    for m in _migrations():
        store.mark_applied(m)

    runner = MigrationRunner(store, migrations=_migrations())
    result = runner.apply_pending(dry_run=True)

    assert result.dry_run_pending == []
    assert result.total_pending == 0
    assert result.ok


def test_migration_result_dry_run_pending_field():
    r = MigrationResult(applied=[], skipped=[], total_pending=2, dry_run_pending=[1, 2])
    assert r.dry_run_pending == [1, 2]
    assert r.ok  # total_pending == len(applied) + len(dry_run_pending) for dry-run path
