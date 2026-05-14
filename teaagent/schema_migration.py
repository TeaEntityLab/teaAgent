from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class SchemaMigration:
    version: int
    description: str
    sql: str


@dataclass(frozen=True)
class MigrationResult:
    applied: list[int]
    skipped: list[int]
    total_pending: int
    dry_run_pending: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.dry_run_pending:
            return len(self.skipped) == 0
        return self.total_pending == len(self.applied)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            'ok': self.ok,
            'applied': self.applied,
            'skipped': self.skipped,
            'total_pending': self.total_pending,
        }
        if self.dry_run_pending:
            result['dry_run_pending'] = self.dry_run_pending
        return result


class SQLiteMigrationStore:
    TABLE = '_teaagent_migrations'

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )

    def applied_versions(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                f'SELECT version FROM {self.TABLE} ORDER BY version'
            ).fetchall()
        return [r[0] for r in rows]

    def mark_applied(self, migration: SchemaMigration) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                f'INSERT OR IGNORE INTO {self.TABLE} (version, description, applied_at) VALUES (?, ?, ?)',
                (migration.version, migration.description, now),
            )

    def status(self, migrations: list[SchemaMigration]) -> dict[str, Any]:
        applied = set(self.applied_versions())
        return {
            'applied': sorted(applied),
            'pending': [m.version for m in migrations if m.version not in applied],
            'total': len(migrations),
        }


class MigrationRunner:
    def __init__(
        self,
        store: SQLiteMigrationStore,
        migrations: list[SchemaMigration],
        *,
        target_conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        self._store = store
        self._migrations = sorted(migrations, key=lambda m: m.version)
        self._target_conn = target_conn

    def apply_pending(self, *, dry_run: bool = False) -> MigrationResult:
        applied_versions = set(self._store.applied_versions())
        pending = [m for m in self._migrations if m.version not in applied_versions]

        if dry_run:
            return MigrationResult(
                applied=[],
                skipped=[],
                total_pending=len(pending),
                dry_run_pending=[m.version for m in pending],
            )

        applied: list[int] = []
        skipped: list[int] = []

        for migration in pending:
            try:
                if self._target_conn is not None:
                    self._target_conn.executescript(migration.sql)
                self._store.mark_applied(migration)
                applied.append(migration.version)
            except Exception:
                skipped.append(migration.version)
                raise

        return MigrationResult(
            applied=applied,
            skipped=skipped,
            total_pending=len(pending),
        )

    def status(self) -> dict[str, Any]:
        return self._store.status(self._migrations)
