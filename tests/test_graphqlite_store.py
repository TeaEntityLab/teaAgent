from __future__ import annotations

from teaagent import (
    Document,
    GraphEdge,
    GraphQLiteConfig,
    GraphQLiteGraphStore,
    KnowledgeGraph,
    check_graphqlite_runtime,
)


class FakeGraphQLiteGraph:
    def __init__(self, database: str) -> None:
        self.database = database
        self.nodes = []
        self.edges = []
        self.queries = []

    def upsert_node(self, node_id, properties, label=None):
        self.nodes.append((node_id, properties, label))

    def upsert_edge(self, source, target, properties, rel_type=None):
        self.edges.append((source, target, properties, rel_type))

    def query(self, cypher, params=None):
        self.queries.append(cypher)
        return [{'ok': True}]


def test_sync_from_knowledge_graph_writes_documents_and_edges() -> None:
    graph = KnowledgeGraph()
    graph.add_document(Document(doc_id='doc-1', text='Alice owns Acme', source='graph'))
    graph.add_edge(
        GraphEdge(
            source='alice', relation='owns', target='acme', document_ids=('doc-1',)
        )
    )
    store = GraphQLiteGraphStore(
        GraphQLiteConfig(database=':memory:'),
        graph_factory=FakeGraphQLiteGraph,
    )

    store.sync_from_knowledge_graph(graph)

    assert store.graph.database == ':memory:'
    assert (
        'doc-1',
        {'doc_id': 'doc-1', 'text': 'Alice owns Acme', 'source': 'graph'},
        'Document',
    ) in store.graph.nodes
    assert (
        'alice',
        'acme',
        {'relation': 'owns', 'document_ids': ['doc-1']},
        'OWNS',
    ) in store.graph.edges


def test_query_delegates_to_graphqlite() -> None:
    store = GraphQLiteGraphStore(graph_factory=FakeGraphQLiteGraph)

    result = store.query('MATCH (n) RETURN n')

    assert result == [{'ok': True}]
    assert store.graph.queries == ['MATCH (n) RETURN n']


def test_real_graphqlite_runtime_smoke_or_reports_environment_issue() -> None:
    available, message = check_graphqlite_runtime()

    assert available, message
    assert message == 'graphqlite runtime is available'


def test_graphqlite_fallback_to_dummy() -> None:
    from unittest.mock import patch

    from teaagent.graphqlite_store import (
        DummyKnowledgeGraph,
        GraphQLiteRuntimeError,
    )

    with patch(
        'teaagent.graphqlite_store.load_graphqlite_graph',
        side_effect=GraphQLiteRuntimeError('missing extensions'),
    ):
        store = GraphQLiteGraphStore(GraphQLiteConfig(database=':memory:'))
        assert isinstance(store.graph, DummyKnowledgeGraph)
        # Ensure it does not crash on ops
        store.upsert_document(
            Document(doc_id='doc-1', text='Alice owns Acme', source='graph')
        )
        assert store.query('MATCH (n) RETURN n') == []
