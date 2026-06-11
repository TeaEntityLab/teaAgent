from __future__ import annotations

import io
import json
import sqlite3
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from teaagent.schema_migration import (
    MigrationResult,
    MigrationRunner,
    SchemaMigration,
    SQLiteMigrationStore,
)


def test_creates_migration_table() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _ = SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')
        conn = sqlite3.connect(str(Path(tmp) / 'db.sqlite3'))
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        conn.close()
        assert '_teaagent_migrations' in tables


def test_applied_versions_empty_initially() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')
        assert store.applied_versions() == []


def test_mark_applied_records_version() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')
        m = SchemaMigration(version=1, description='init', sql='')
        store.mark_applied(m)
        assert store.applied_versions() == [1]


def test_mark_applied_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')
        m = SchemaMigration(version=1, description='init', sql='')
        store.mark_applied(m)
        store.mark_applied(m)
        assert store.applied_versions() == [1]


def test_status_reports_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')
        migrations = [
            SchemaMigration(1, 'a', ''),
            SchemaMigration(2, 'b', ''),
        ]
        store.mark_applied(migrations[0])
        status = store.status(migrations)
        assert status['applied'] == [1]
        assert status['pending'] == [2]


def test_persists_across_instances() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'db.sqlite3'
        m = SchemaMigration(version=3, description='test', sql='')
        SQLiteMigrationStore(path).mark_applied(m)
        assert SQLiteMigrationStore(path).applied_versions() == [3]


def _store(tmp: str) -> SQLiteMigrationStore:
    return SQLiteMigrationStore(Path(tmp) / 'db.sqlite3')


def test_apply_pending_runs_new_migrations() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        conn = sqlite3.connect(str(Path(tmp) / 'app.sqlite3'))
        migrations = [
            SchemaMigration(
                1,
                'create table',
                'CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);',
            ),
        ]
        runner = MigrationRunner(store, migrations, target_conn=conn)
        result = runner.apply_pending()
        assert result.applied == [1]
        assert result.skipped == []
        assert result.ok is True
        conn.close()


def test_apply_pending_skips_already_applied() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        m = SchemaMigration(1, 'already done', '')
        store.mark_applied(m)
        runner = MigrationRunner(store, [m])
        result = runner.apply_pending()
        assert result.applied == []
        assert result.total_pending == 0


def test_migrations_run_in_version_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        applied_order: list[int] = []

        class TrackingMigration(SchemaMigration):
            pass

        migrations = [
            SchemaMigration(3, 'c', ''),
            SchemaMigration(1, 'a', ''),
            SchemaMigration(2, 'b', ''),
        ]

        class TrackingRunner(MigrationRunner):
            def apply_pending(self):
                applied = set(self._store.applied_versions())
                pending = [m for m in self._migrations if m.version not in applied]
                for m in pending:
                    applied_order.append(m.version)
                    self._store.mark_applied(m)
                return MigrationResult(
                    applied=[m.version for m in pending],
                    skipped=[],
                    total_pending=len(pending),
                )

        TrackingRunner(store, migrations).apply_pending()
        assert applied_order == [1, 2, 3]


def test_status_returns_correct_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = _store(tmp)
        migrations = [SchemaMigration(i, f'm{i}', '') for i in range(1, 4)]
        store.mark_applied(migrations[0])
        runner = MigrationRunner(store, migrations)
        status = runner.status()
        assert 2 in status['pending']
        assert 3 in status['pending']
        assert 1 in status['applied']


def test_doctor_migration_without_store_returns_error() -> None:
    from teaagent.cli import main

    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(['doctor', 'migration'])
    assert exit_code == 1
    payload = json.loads(output.getvalue())
    assert payload['ok'] is False


def test_doctor_migration_with_store_returns_ok() -> None:
    from teaagent.cli import main

    with tempfile.TemporaryDirectory() as tmp:
        store_path = str(Path(tmp) / 'db.sqlite3')
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['doctor', 'migration', '--store', store_path])
    assert exit_code == 0
    payload = json.loads(output.getvalue())
    assert payload['ok'] is True
    assert 'status' in payload
