"""Context Bus - Cross-sandbox Delta sharing for parallel agents.

This module implements the Cooragent context bus that:
1. Provides real-time Delta sharing between parallel Sandbox agents
2. Uses WAL-mode SQLite for concurrent access
3. Manages Delta lifecycle (broadcast during workflow, archive to RAG after)
4. Integrates with ACI for context injection
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
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure database directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the context bus database schema."""
        with self._lock:
            self._connection = sqlite3.connect(
                self._db_path, check_same_thread=False, timeout=5.0
            )
            cursor = self._connection.cursor()

            # Enable WAL mode for concurrent access
            if self._config.enable_wal_mode:
                cursor.execute('PRAGMA journal_mode=WAL')
                cursor.execute('PRAGMA synchronous=NORMAL')

            # Create Delta cards table
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

            # Create indexes
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_workflow_id ON delta_cards(workflow_id)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_source_agent ON delta_cards(source_agent)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_timestamp ON delta_cards(timestamp)'
            )

            self._connection.commit()

    def _execute_with_retry(
        self,
        cursor: sqlite3.Cursor,
        sql: str,
        params: tuple[Any, ...] = (),
        *,
        max_retries: int = 5,
        base_delay: float = 0.1,
    ) -> sqlite3.Cursor:
        """Execute a SQL statement with exponential backoff on lock contention.

        Returns:
            Cursor (potentially a new cursor after a reconnect).
        """
        for attempt in range(max_retries):
            try:
                cursor.execute(sql, params)
                return cursor
            except sqlite3.DatabaseError as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        f'SQLite database error failed after reconnect attempts: {exc}'
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    f'SQLite database error (attempt {attempt + 1}/{max_retries}), reconnecting: {exc}'
                )
                with suppress(Exception):
                    cursor.connection.rollback()
                time.sleep(delay)
                self._reconnect()
                assert self._connection is not None
                cursor = self._connection.cursor()
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
                    raise
                if attempt == max_retries - 1:
                    logger.error(
                        f'SQLite operation failed after {max_retries} retries: {exc}'
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    f'SQLite lock contention (attempt {attempt + 1}/{max_retries}), '
                    f'retrying in {delay:.2f}s'
                )
                with suppress(Exception):
                    cursor.connection.rollback()
                time.sleep(delay)

        raise RuntimeError(
            'Unexpected: _execute_with_retry loop exited without returning or raising'
        )

    def _commit_with_retry(
        self,
        conn: sqlite3.Connection,
        *,
        max_retries: int = 5,
        base_delay: float = 0.1,
    ) -> None:
        """Commit with exponential backoff on lock contention."""
        for attempt in range(max_retries):
            try:
                conn.commit()
                return
            except sqlite3.DatabaseError as exc:
                if attempt == max_retries - 1:
                    logger.error(f'SQLite commit database error failed: {exc}')
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    f'SQLite commit database error (attempt {attempt + 1}/{max_retries}): {exc}'
                )
                with suppress(Exception):
                    conn.rollback()
                time.sleep(delay)
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() and 'busy' not in str(exc).lower():
                    raise
                if attempt == max_retries - 1:
                    logger.error(
                        f'SQLite commit failed after {max_retries} retries: {exc}'
                    )
                    raise
                delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                logger.warning(
                    f'SQLite commit contention (attempt {attempt + 1}/{max_retries}), '
                    f'retrying in {delay:.2f}s'
                )
                with suppress(Exception):
                    conn.rollback()
                time.sleep(delay)

    def _reconnect(self) -> None:
        """Reconnect to the database after corruption or file deletion."""
        if self._connection:
            with suppress(Exception):
                self._connection.close()
        self._connection = sqlite3.connect(
            self._db_path, check_same_thread=False, timeout=5.0
        )
        cursor = self._connection.cursor()
        if self._config.enable_wal_mode:
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
        self._connection.commit()
        logger.warning('Reconnected to context bus database')

    def publish_delta(self, delta: DeltaCard) -> None:
        """Publish a Delta card to the bus ensuring no transactions are leaked.

        Args:
            delta: DeltaCard to publish.
        """
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            with self._lock:
                conn = self._connection
                if conn is None:
                    raise RuntimeError('Context bus connection is not initialized')
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
                        f'Published Delta {delta.delta_id} from {delta.source_agent}'
                    )
                    return
                except sqlite3.Error as exc:
                    with suppress(Exception):
                        conn.rollback()
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                    logger.warning(
                        f'publish_delta failed (attempt {attempt + 1}/{max_retries}): {exc}, '
                        f'reconnecting and retrying in {delay:.2f}s'
                    )
                    self._reconnect()

            # Sleep outside the lock to avoid thread starvation
            time.sleep(delay)

    def subscribe_deltas(
        self,
        source_agent: Optional[str] = None,
        delta_type: Optional[DeltaType] = None,
        since_timestamp: Optional[float] = None,
    ) -> list[DeltaCard]:
        """Subscribe to Delta cards from the bus.

        Args:
            source_agent: Filter by source agent (optional).
            delta_type: Filter by delta type (optional).
            since_timestamp: Filter by timestamp (optional).

        Returns:
            List of matching Delta cards.
        """
        with self._lock:
            conn = self._connection
            if conn is None:
                raise RuntimeError('Context bus connection is not initialized')
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
        """Archive Delta cards to RAG long-term memory.

        Args:
            rag_store: RAG store to archive to.
        """
        deltas = self.subscribe_deltas()
        max_timestamp = max((d.timestamp for d in deltas), default=None)

        for delta in deltas:
            # Convert Delta to RAG document
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

            # Add to RAG store (implementation depends on RAG interface)
            try:
                if hasattr(rag_store, 'add_document'):
                    rag_store.add_document(rag_doc)
                elif hasattr(rag_store, 'add'):
                    rag_store.add(rag_doc)
                else:
                    logger.warning('RAG store does not support adding documents')
            except Exception as exc:
                logger.error(f'Failed to archive Delta to RAG: {exc}')

        # Clear Delta cards after archiving (only those up to the batch timestamp)
        self._clear_deltas(max_timestamp=max_timestamp)

        logger.info(f'Archived {len(deltas)} Delta cards to RAG')

    def _clear_deltas(self, max_timestamp: Optional[float] = None) -> None:
        """Clear all Delta cards for the current workflow.

        Args:
            max_timestamp: If set, only clear deltas with timestamp <= this value.
        """
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            with self._lock:
                conn = self._connection
                if conn is None:
                    raise RuntimeError('Context bus connection is not initialized')
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
                        f'_clear_deltas failed (attempt {attempt + 1}/{max_retries}): {exc}, '
                        f'reconnecting and retrying in {delay:.2f}s'
                    )
                    self._reconnect()

            # Sleep outside the lock to avoid thread starvation
            time.sleep(delay)

    def cleanup_old_deltas(self) -> None:
        """Clean up old Delta cards based on age."""
        cutoff_time = time.time() - self._config.max_delta_age_seconds
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            with self._lock:
                conn = self._connection
                if conn is None:
                    raise RuntimeError('Context bus connection is not initialized')
                cursor = conn.cursor()

                try:
                    cursor.execute(
                        'DELETE FROM delta_cards WHERE timestamp < ?',
                        (cutoff_time,),
                    )
                    deleted = cursor.rowcount
                    conn.commit()
                    if deleted > 0:
                        logger.info(f'Cleaned up {deleted} old Delta cards')
                    return
                except sqlite3.Error as exc:
                    with suppress(Exception):
                        conn.rollback()
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2**attempt) + random.uniform(0, 0.05)
                    logger.warning(
                        f'cleanup_old_deltas failed (attempt {attempt + 1}/{max_retries}): {exc}, '
                        f'reconnecting and retrying in {delay:.2f}s'
                    )
                    self._reconnect()

            # Sleep outside the lock to avoid thread starvation
            time.sleep(delay)

    def get_delta_count(self) -> int:
        """Get the count of Delta cards for the current workflow.

        Returns:
            Number of Delta cards.
        """
        with self._lock:
            conn = self._connection
            if conn is None:
                raise RuntimeError('Context bus connection is not initialized')
            cursor = conn.cursor()
            cursor = self._execute_with_retry(
                cursor,
                'SELECT COUNT(*) FROM delta_cards WHERE workflow_id = ?',
                (self._workflow_id,),
            )
            return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the context bus connection."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                logger.info('Context bus connection closed')
