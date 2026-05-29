"""Context Bus - Cross-sandbox Delta sharing for parallel agents.

This module implements the Cooragent context bus that:
1. Provides real-time Delta sharing between parallel Sandbox agents
2. Uses WAL-mode SQLite for concurrent access
3. Manages Delta lifecycle (broadcast during workflow, archive to RAG after)
4. Integrates with ACI for context injection

Each thread uses its own SQLite connection (``threading.local``) so parallel
agents do not share one connection object. A generation counter invalidates
stale handles after ``_reconnect``.
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SQLITE_TIMEOUT_SECONDS = 5.0


class DeltaType(Enum):
    """Types of Delta cards."""

    CODE_CHANGE = 'code_change'
    DISCOVERY = 'discovery'
    ERROR = 'error'
    SUCCESS = 'success'
    CONTEXT_UPDATE = 'context_update'


@dataclass
class DeltaCard:
    """A Delta card shared between agents."""

    delta_id: str
    delta_type: DeltaType
    source_agent: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextBusConfig:
    """Configuration for the context bus."""

    db_path: Path
    workflow_id: str
    max_delta_age_seconds: int = 3600  # 1 hour default
    enable_wal_mode: bool = True


class ContextBus:
    """Manages real-time Delta sharing between parallel agents."""

    def __init__(self, config: ContextBusConfig) -> None:
        self._config = config
        self._db_path = config.db_path
        self._workflow_id = config.workflow_id
        self._lock = threading.Lock()
        self._thread_local = threading.local()
        self._all_connections: set[sqlite3.Connection] = set()
        self._connection_generation = 0

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Apply WAL and durability pragmas on a new connection."""
        if not self._config.enable_wal_mode:
            return
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        conn.commit()

    def _new_connection(self) -> sqlite3.Connection:
        """Open, configure, and register a new SQLite connection."""
        conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=_SQLITE_TIMEOUT_SECONDS,
        )
        self._configure_connection(conn)
        with self._lock:
            self._all_connections.add(conn)
        return conn

    def _initialize_database(self) -> None:
        """Initialize the context bus database schema."""
        conn = self._new_connection()
        with self._lock:
            generation = self._connection_generation
        self._thread_local.connection = conn
        self._thread_local.generation = generation
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS delta_cards (
                delta_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                delta_type TEXT NOT NULL,
                source_agent TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT
            )
        """
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_workflow_id ON delta_cards(workflow_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_source_agent ON delta_cards(source_agent)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_timestamp ON delta_cards(timestamp)'
        )
        conn.commit()

    def _execute_with_retry(
        self,
        cursor: sqlite3.Cursor,
        sql: str,
        params: tuple[Any, ...] = (),
        *,
        max_retries: int = 5,
        base_delay: float = 0.1,
    ) -> sqlite3.Cursor:
        """Execute a SQL statement with exponential backoff on lock contention."""
        for attempt in range(max_retries):
            try:
                cursor.execute(sql, params)
                return cursor
            except sqlite3.DatabaseError as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        'SQLite database error failed after reconnect attempts: %s',
                        exc,
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    'SQLite database error (attempt %s/%s), reconnecting: %s',
                    attempt + 1,
                    max_retries,
                    exc,
                )
                with suppress(Exception):
                    cursor.connection.rollback()
                time.sleep(delay)
                with self._lock:
                    self._reconnect()
                cursor = self._get_connection().cursor()
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
                    raise
                if attempt == max_retries - 1:
                    logger.error(
                        'SQLite operation failed after %s retries: %s',
                        max_retries,
                        exc,
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    'SQLite lock contention (attempt %s/%s), retrying in %.2fs',
                    attempt + 1,
                    max_retries,
                    delay,
                )
                with suppress(Exception):
                    cursor.connection.rollback()
                time.sleep(delay)

        raise RuntimeError(
            'Unexpected: _execute_with_retry loop exited without returning or raising'
        )

    def _reconnect(self) -> None:
        """Close the current thread's connection and bump generation.

        Other threads refresh lazily on next ``_get_connection`` (P2.1).
        Caller must hold ``_lock``.
        """
        conn = getattr(self._thread_local, 'connection', None)
        if conn is not None:
            with suppress(Exception):
                conn.close()
            self._all_connections.discard(conn)
        if hasattr(self._thread_local, 'connection'):
            del self._thread_local.connection
        if hasattr(self._thread_local, 'generation'):
            del self._thread_local.generation
        self._connection_generation += 1
        logger.warning('Reconnected to context bus database')

    def _get_connection(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, refreshing after reconnect."""
        with self._lock:
            generation = self._connection_generation
        conn = getattr(self._thread_local, 'connection', None)
        local_gen = getattr(self._thread_local, 'generation', None)
        if conn is not None and local_gen == generation:
            return conn
        if conn is not None:
            with suppress(Exception):
                conn.close()
            with self._lock:
                self._all_connections.discard(conn)
        conn = self._new_connection()
        self._thread_local.connection = conn
        self._thread_local.generation = generation
        return conn

    def publish_delta(self, delta: DeltaCard) -> None:
        """Publish a Delta card to the bus ensuring no transactions are leaked."""
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO delta_cards
                    (delta_id, workflow_id, delta_type, source_agent, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        delta.delta_id,
                        self._workflow_id,
                        delta.delta_type.value,
                        delta.source_agent,
                        delta.content,
                        delta.timestamp,
                        json.dumps(delta.metadata),
                    ),
                )
                conn.commit()
                logger.info(
                    'Published Delta %s from %s', delta.delta_id, delta.source_agent
                )
                return
            except sqlite3.Error as exc:
                with suppress(Exception):
                    conn.rollback()
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    'publish_delta failed (attempt %s/%s): %s, reconnecting in %.2fs',
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                with self._lock:
                    self._reconnect()
                time.sleep(delay)

    def subscribe_deltas(
        self,
        source_agent: Optional[str] = None,
        delta_type: Optional[DeltaType] = None,
        since_timestamp: Optional[float] = None,
    ) -> list[DeltaCard]:
        """Subscribe to Delta cards from the bus."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM delta_cards WHERE workflow_id = ?'
        params: list[Any] = [self._workflow_id]

        if source_agent:
            query += ' AND source_agent = ?'
            params.append(source_agent)

        if delta_type:
            query += ' AND delta_type = ?'
            params.append(delta_type.value)

        if since_timestamp:
            query += ' AND timestamp >= ?'
            params.append(since_timestamp)

        query += ' ORDER BY timestamp DESC'

        cursor = self._execute_with_retry(cursor, query, tuple(params))
        rows = cursor.fetchall()

        deltas = []
        for row in rows:
            deltas.append(
                DeltaCard(
                    delta_id=row[0],
                    delta_type=DeltaType(row[2]),
                    source_agent=row[3],
                    content=row[4],
                    timestamp=row[5],
                    metadata=json.loads(row[6]) if row[6] else {},
                )
            )

        return deltas

    def archive_to_rag(self, rag_store: Any) -> None:
        """Archive Delta cards to RAG long-term memory."""
        deltas = self.subscribe_deltas()
        max_timestamp = max((d.timestamp for d in deltas), default=None)

        for delta in deltas:
            rag_doc = {
                'doc_id': delta.delta_id,
                'source': delta.source_agent,
                'content': delta.content,
                'metadata': {
                    **delta.metadata,
                    'delta_type': delta.delta_type.value,
                    'timestamp': delta.timestamp,
                    'workflow_id': self._workflow_id,
                },
            }

            try:
                if hasattr(rag_store, 'add_document'):
                    rag_store.add_document(rag_doc)
                elif hasattr(rag_store, 'add'):
                    rag_store.add(rag_doc)
                else:
                    logger.warning('RAG store does not support adding documents')
            except Exception as exc:
                logger.error('Failed to archive Delta to RAG: %s', exc)

        self._clear_deltas(max_timestamp=max_timestamp)
        logger.info('Archived %s Delta cards to RAG', len(deltas))

    def _clear_deltas(self, max_timestamp: Optional[float] = None) -> None:
        """Clear Delta cards for the current workflow."""
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                if max_timestamp is not None:
                    cursor.execute(
                        'DELETE FROM delta_cards WHERE workflow_id = ? AND timestamp <= ?',
                        (self._workflow_id, max_timestamp),
                    )
                else:
                    cursor.execute(
                        'DELETE FROM delta_cards WHERE workflow_id = ?',
                        (self._workflow_id,),
                    )
                conn.commit()
                return
            except sqlite3.Error as exc:
                with suppress(Exception):
                    conn.rollback()
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    '_clear_deltas failed (attempt %s/%s): %s, reconnecting in %.2fs',
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                with self._lock:
                    self._reconnect()
                time.sleep(delay)

    def cleanup_old_deltas(self) -> None:
        """Clean up old Delta cards based on age."""
        cutoff_time = time.time() - self._config.max_delta_age_seconds
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            conn = self._get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute(
                    'DELETE FROM delta_cards WHERE workflow_id = ? AND timestamp < ?',
                    (self._workflow_id, cutoff_time),
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    logger.info('Cleaned up %s old Delta cards', deleted)
                return
            except sqlite3.Error as exc:
                with suppress(Exception):
                    conn.rollback()
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    'cleanup_old_deltas failed (attempt %s/%s): %s, reconnecting in %.2fs',
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                with self._lock:
                    self._reconnect()
                time.sleep(delay)

    def get_delta_count(self) -> int:
        """Get the count of Delta cards for the current workflow."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor = self._execute_with_retry(
            cursor,
            'SELECT COUNT(*) FROM delta_cards WHERE workflow_id = ?',
            (self._workflow_id,),
        )
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close all context bus connections."""
        with self._lock:
            for conn in list(self._all_connections):
                with suppress(Exception):
                    conn.close()
            self._all_connections.clear()
            self._connection_generation += 1
            if hasattr(self._thread_local, 'connection'):
                del self._thread_local.connection
            if hasattr(self._thread_local, 'generation'):
                del self._thread_local.generation
            logger.info('Context bus connections closed')
