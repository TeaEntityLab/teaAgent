from __future__ import annotations

import contextlib
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Optional

from teaagent.graph_rag import GraphEdge, KnowledgeGraph
from teaagent.graphqlite_store import (
    GraphFactory,
    GraphQLiteConfig,
    GraphQLiteGraphStore,
)
from teaagent.rag import Document, RetrievalResult, tokenize
from teaagent.schema_migration import (
    MigrationRunner,
    SchemaMigration,
    SQLiteMigrationStore,
)

logger = logging.getLogger(__name__)

_PRODUCTION_PRAGMAS: tuple[str, ...] = (
    'PRAGMA journal_mode=WAL',
    'PRAGMA synchronous=NORMAL',
    'PRAGMA busy_timeout=5000',
    'PRAGMA cache_size=-2000',
    'PRAGMA foreign_keys=ON',
)

_GRAPHQLITE_SCHEMA_MIGRATIONS: tuple[SchemaMigration, ...] = (
    SchemaMigration(
        version=1,
        description='Base graph schema: Document nodes, Entity nodes, typed relationships',
        sql=(
            'CREATE TABLE IF NOT EXISTS _gql_meta (key TEXT PRIMARY KEY, value TEXT);\n'
            "INSERT OR IGNORE INTO _gql_meta (key, value) VALUES ('schema_version', '1')"
        ),
    ),
    SchemaMigration(
        version=2,
        description='Index on Entity(name) for entity-lookup traversal',
        sql='CREATE INDEX IF NOT EXISTS idx_entity_name ON Entity(name)',
    ),
    SchemaMigration(
        version=3,
        description='Index on Document(source) for source-filtered retrieval',
        sql='CREATE INDEX IF NOT EXISTS idx_document_source ON Document(source)',
    ),
    SchemaMigration(
        version=4,
        description='Index on Document(doc_id) for document lookups',
        sql='CREATE INDEX IF NOT EXISTS idx_document_doc_id ON Document(doc_id)',
    ),
    SchemaMigration(
        version=5,
        description='Index on EDGE(relation) for relationship-type traversal',
        sql='CREATE INDEX IF NOT EXISTS idx_edge_relation ON EDGE(relation)',
    ),
    SchemaMigration(
        version=6,
        description='Create prefetch_cache table for time-based retrieval optimization',
        sql=(
            'CREATE TABLE IF NOT EXISTS prefetch_cache (\n'
            '    doc_id TEXT PRIMARY KEY,\n'
            '    text TEXT NOT NULL,\n'
            '    source TEXT NOT NULL,\n'
            '    created_at TEXT NOT NULL,\n'
            '    metadata TEXT\n'
            ');\n'
            'CREATE INDEX IF NOT EXISTS idx_prefetch_created_at ON prefetch_cache(created_at);\n'
            'CREATE INDEX IF NOT EXISTS idx_prefetch_source ON prefetch_cache(source);'
        ),
    ),
)


@dataclass(frozen=True)
class GraphQLiteProductionConfig:
    database: str
    auto_migrate: bool = True
    auto_index: bool = True
    pragmas: tuple[str, ...] = field(default_factory=lambda: _PRODUCTION_PRAGMAS)


class GraphQLitePersistentStore(GraphQLiteGraphStore):
    def __init__(
        self,
        config: Optional[GraphQLiteProductionConfig] = None,
        *,
        graph_factory: Optional[GraphFactory] = None,
    ) -> None:
        self._prod_config = config or GraphQLiteProductionConfig(database=':memory:')
        graphqlite_config = GraphQLiteConfig(database=self._prod_config.database)
        super().__init__(graphqlite_config, graph_factory=graph_factory)

        if self._prod_config.auto_index and self._prod_config.database != ':memory:':
            self._ensure_indexes()

        if self._prod_config.auto_migrate and self._prod_config.database != ':memory:':
            self._apply_migrations()

    def _ensure_indexes(self) -> None:
        for mig in _GRAPHQLITE_SCHEMA_MIGRATIONS[1:]:
            with contextlib.suppress(sqlite3.Error, OSError):
                self.graph.query(mig.sql)

    def _apply_migrations(self) -> None:
        store = SQLiteMigrationStore(self._prod_config.database)
        conn = sqlite3.connect(self._prod_config.database)
        try:
            runner = MigrationRunner(store, list(_GRAPHQLITE_SCHEMA_MIGRATIONS), target_conn=conn)
            runner.apply_pending()
        finally:
            conn.close()

    def migration_status(self) -> dict[str, Any]:
        if self._prod_config.database == ':memory:':
            return {
                'applied': [],
                'pending': [m.version for m in _GRAPHQLITE_SCHEMA_MIGRATIONS],
                'total': len(_GRAPHQLITE_SCHEMA_MIGRATIONS),
            }
        store = SQLiteMigrationStore(self._prod_config.database)
        return store.status(list(_GRAPHQLITE_SCHEMA_MIGRATIONS))

    def graph_retrieve(
        self, query: str, *, max_depth: int = 2, limit: int = 5
    ) -> list[RetrievalResult]:
        query_terms = set(tokenize(query))
        scored: dict[str, RetrievalResult] = {}

        for term in query_terms:
            try:
                cypher = (
                    f"MATCH p=(a:Entity {{name: '{term}'}})"
                    f'-[*1..{max_depth}]-(b:Entity) '
                    f'RETURN nodes(p) as nodes, relationships(p) as rels'
                )
                results = self.graph.query(cypher)
            except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
                logger.debug('Graph query failed for term %s: %s', term, exc)
                continue

            for row in results:
                doc_ids = self._collect_doc_ids_from_rels(row.get('rels', []))
                path_nodes = row.get('nodes', [])
                rels_list = row.get('rels', [])
                path_text = (
                    ' '.join(
                        str(n.get('name', '')) if isinstance(n, dict) else ''
                        for n in path_nodes
                    )
                    + ' '
                    + ' '.join(
                        str(r.get('relation', '')) if isinstance(r, dict) else ''
                        for r in rels_list
                    )
                )
                path_terms = set(tokenize(path_text))
                score = len(query_terms & path_terms) / max(len(query_terms), 1)
                for doc_id in doc_ids:
                    doc_data = self._fetch_document(doc_id)
                    if not doc_data:
                        continue
                    doc = Document(
                        doc_id=doc_data.get('doc_id', doc_id),
                        text=doc_data.get('text', ''),
                        source=doc_data.get('source', ''),
                        metadata={
                            k: str(v)
                            for k, v in doc_data.items()
                            if k not in ('doc_id', 'text', 'source')
                        },
                    )
                    existing = scored.get(doc_id)
                    if existing is None or score > existing.score:
                        scored[doc_id] = RetrievalResult(
                            document=doc, score=score, query=query
                        )

        return sorted(scored.values(), key=lambda r: r.score, reverse=True)[:limit]

    def _collect_doc_ids_from_rels(self, rels: list[Any]) -> set[str]:
        doc_ids: set[str] = set()
        for rel in rels:
            if isinstance(rel, dict):
                ids = rel.get('document_ids')
                if isinstance(ids, (list, tuple)):
                    doc_ids.update(ids)
        return doc_ids

    def _fetch_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        try:
            safe_doc_id = doc_id.replace("'", "''")
            results = self.graph.query(
                f"MATCH (d:Document {{doc_id: '{safe_doc_id}'}}) RETURN d"
            )
            if results:
                return results[0].get('d', {})
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            logger.debug('Failed to fetch document %s: %s', doc_id, exc)
        return None

    def sync_to_knowledge_graph(self, knowledge_graph: KnowledgeGraph) -> None:
        try:
            doc_rows = self.graph.query('MATCH (d:Document) RETURN d')
            for row in doc_rows:
                d = row.get('d', {})
                knowledge_graph.add_document(
                    Document(
                        doc_id=d.get('doc_id', ''),
                        text=d.get('text', ''),
                        source=d.get('source', ''),
                        metadata={
                            k: str(v)
                            for k, v in d.items()
                            if k not in ('doc_id', 'text', 'source')
                        },
                    )
                )
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            logger.warning('Failed to sync documents to knowledge graph: %s', exc)

        try:
            edge_rows = self.graph.query(
                'MATCH (a:Entity)-[r]->(b:Entity) '
                'RETURN a.name as source, r.relation as relation, '
                'b.name as target, r.document_ids as doc_ids'
            )
            for row in edge_rows:
                knowledge_graph.add_edge(
                    GraphEdge(
                        source=row.get('source', ''),
                        relation=row.get('relation', ''),
                        target=row.get('target', ''),
                        document_ids=tuple(row.get('doc_ids', [])),
                    )
                )
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            logger.warning('Failed to sync edges to knowledge graph: %s', exc)
