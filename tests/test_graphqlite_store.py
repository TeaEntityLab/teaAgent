from __future__ import annotations

import unittest

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

    def query(self, cypher):
        self.queries.append(cypher)
        return [{"ok": True}]


class GraphQLiteStoreTests(unittest.TestCase):
    def test_sync_from_knowledge_graph_writes_documents_and_edges(self) -> None:
        graph = KnowledgeGraph()
        graph.add_document(Document(doc_id="doc-1", text="Alice owns Acme", source="graph"))
        graph.add_edge(GraphEdge(source="alice", relation="owns", target="acme", document_ids=("doc-1",)))
        store = GraphQLiteGraphStore(
            GraphQLiteConfig(database=":memory:"),
            graph_factory=FakeGraphQLiteGraph,
        )

        store.sync_from_knowledge_graph(graph)

        self.assertEqual(store.graph.database, ":memory:")
        self.assertIn(("doc-1", {"doc_id": "doc-1", "text": "Alice owns Acme", "source": "graph"}, "Document"), store.graph.nodes)
        self.assertIn(("alice", "acme", {"relation": "owns", "document_ids": ["doc-1"]}, "OWNS"), store.graph.edges)

    def test_query_delegates_to_graphqlite(self) -> None:
        store = GraphQLiteGraphStore(graph_factory=FakeGraphQLiteGraph)

        result = store.query("MATCH (n) RETURN n")

        self.assertEqual(result, [{"ok": True}])
        self.assertEqual(store.graph.queries, ["MATCH (n) RETURN n"])

    def test_real_graphqlite_runtime_smoke_or_reports_environment_issue(self) -> None:
        available, message = check_graphqlite_runtime()

        self.assertTrue(available, message)
        self.assertEqual(message, "graphqlite runtime is available")


if __name__ == "__main__":
    unittest.main()
