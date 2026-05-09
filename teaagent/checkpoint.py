from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_CHECKPOINT_KEYS = ('task', 'observations', 'compacted_summary', 'memory_keys')
_SCHEMA_VERSION = 1


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def save(self, run_id: str, context: dict[str, Any]) -> None:
        self._data[run_id] = _extract_checkpoint(context)

    def load(self, run_id: str) -> Optional[dict[str, Any]]:
        return self._data.get(run_id)

    def delete(self, run_id: str) -> None:
        self._data.pop(run_id, None)


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY,
                    context_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def save(self, run_id: str, context: dict[str, Any]) -> None:
        snapshot = _extract_checkpoint(context)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (run_id, context_json, updated_at, schema_version)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    context_json = excluded.context_json,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    json.dumps(snapshot, ensure_ascii=False),
                    now,
                    _SCHEMA_VERSION,
                ),
            )

    def load(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT context_json FROM checkpoints WHERE run_id = ?',
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def delete(self, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM checkpoints WHERE run_id = ?', (run_id,))


def _extract_checkpoint(context: dict[str, Any]) -> dict[str, Any]:
    return {k: context[k] for k in _CHECKPOINT_KEYS if k in context}
