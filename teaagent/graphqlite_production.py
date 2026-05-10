from __future__ import annotations

import contextlib
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
            with contextlib.suppress(Exception):
                self.graph.query(mig.sql)

    def _apply_migrations(self) -> None:
        store = SQLiteMigrationStore(self._prod_config.database)
        runner = MigrationRunner(store, list(_GRAPHQLITE_SCHEMA_MIGRATIONS))
        runner.apply_pending()

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
            except Exception:
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
            results = self.graph.query(
                f"MATCH (d:Document {{doc_id: '{doc_id}'}}) RETURN d"
            )
            if results:
                return results[0].get('d', {})
        except Exception:
            pass
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
        except Exception:
            pass

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
        except Exception:
            pass
