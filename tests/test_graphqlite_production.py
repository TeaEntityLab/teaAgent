from __future__ import annotations

from teaagent import Document, KnowledgeGraph
from teaagent.graphqlite_production import (
    GraphQLitePersistentStore,
    GraphQLiteProductionConfig,
)


class FakeGraphQLiteGraph:
    def __init__(self, database: str) -> None:
        self.database = database
        self.nodes: list[tuple] = []
        self.edges: list[tuple] = []
        self.queries: list[str] = []

    def upsert_node(
        self, node_id: str, properties: dict, label: str | None = None
    ) -> None:
        self.nodes.append((node_id, properties, label))

    def upsert_edge(
        self, source: str, target: str, properties: dict, rel_type: str | None = None
    ) -> None:
        self.edges.append((source, target, properties, rel_type))

    def query(self, cypher: str, params: dict | None = None):
        self.queries.append(cypher)
        if 'MATCH (d:Document' in cypher:
            if "doc_id: '" in cypher:
                doc_id = cypher.split("doc_id: '")[1].split("'")[0]
                return [
                    {
                        'd': {
                            'doc_id': doc_id,
                            'text': 'Alice owns Acme Inc.',
                            'source': 'graph',
                        }
                    }
                ]
            return [
                {
                    'd': {
                        'doc_id': 'doc-1',
                        'text': 'Alice owns Acme Inc.',
                        'source': 'graph',
                    }
                }
            ]
        if 'MATCH (a:Entity)-[r]->(b:Entity)' in cypher:
            return [
                {
                    'source': 'alice',
                    'relation': 'OWNS',
                    'target': 'acme',
                    'doc_ids': ['doc-1'],
                }
            ]
        if 'MATCH (d:Document) RETURN d' in cypher:
            return [
                {
                    'd': {
                        'doc_id': 'doc-1',
                        'text': 'Alice owns Acme Inc.',
                        'source': 'graph',
                    }
                }
            ]
        if 'nodes(p)' in cypher:
            name = (params or {}).get('term', 'alice')
            return [
                {
                    'nodes': [{'name': name}, {'name': 'acme'}],
                    'rels': [{'relation': 'OWNS', 'document_ids': ['doc-1']}],
                }
            ]
        return []


def test_sync_from_and_to_knowledge_graph() -> None:
    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(database=':memory:'),
        graph_factory=FakeGraphQLiteGraph,
    )

    graph = KnowledgeGraph()
    graph.add_document(
        Document(doc_id='doc-1', text='Alice owns Acme Inc.', source='graph')
    )
    store.sync_from_knowledge_graph(graph)

    graph2 = KnowledgeGraph()
    store.sync_to_knowledge_graph(graph2)
    assert len(graph2.all_documents()) == 1
    assert graph2.all_documents()[0].doc_id == 'doc-1'


def test_graph_retrieve_from_fake_store() -> None:
    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(database=':memory:'),
        graph_factory=FakeGraphQLiteGraph,
    )

    results = store.graph_retrieve('alice', max_depth=2, limit=5)
    assert len(results) == 1
    assert results[0].document.doc_id == 'doc-1'
    assert results[0].score > 0


def test_migration_status_on_memory_store() -> None:
    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(database=':memory:'),
        graph_factory=FakeGraphQLiteGraph,
    )

    status = store.migration_status()
    assert 'applied' in status
    assert 'pending' in status
    assert 'total' in status


def test_persistent_store_skips_migrations_on_memory() -> None:
    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(
            database=':memory:', auto_migrate=True, auto_index=True
        ),
        graph_factory=FakeGraphQLiteGraph,
    )

    for query in store.graph.queries:
        assert 'CREATE INDEX' not in query


def test_fetch_document_from_store() -> None:
    store = GraphQLitePersistentStore(
        GraphQLiteProductionConfig(database=':memory:'),
        graph_factory=FakeGraphQLiteGraph,
    )

    doc = store._fetch_document('doc-1')
    assert doc is not None
    assert doc['doc_id'] == 'doc-1'
