from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any, Callable, Optional

from teaagent.graph_rag import GraphEdge, KnowledgeGraph
from teaagent.rag import Document


class GraphQLiteUnavailableError(ImportError):
    pass


class GraphQLiteRuntimeError(RuntimeError):
    pass


GraphFactory = Callable[[str], Any]


@dataclass(frozen=True)
class GraphQLiteConfig:
    database: str = ":memory:"


class GraphQLiteGraphStore:
    """GraphQLite-backed store for Graph RAG entity and relation data."""

    def __init__(self, config: Optional[GraphQLiteConfig] = None, *, graph_factory: Optional[GraphFactory] = None) -> None:
        self.config = config or GraphQLiteConfig()
        self.graph = (graph_factory or load_graphqlite_graph)(self.config.database)

    def upsert_document(self, document: Document) -> None:
        self.graph.upsert_node(
            document.doc_id,
            {
                "doc_id": document.doc_id,
                "text": document.text,
                "source": document.source,
                **document.metadata,
            },
            label="Document",
        )

    def upsert_edge(self, edge: GraphEdge) -> None:
        self.graph.upsert_node(edge.source, {"name": edge.source}, label="Entity")
        self.graph.upsert_node(edge.target, {"name": edge.target}, label="Entity")
        self.graph.upsert_edge(
            edge.source,
            edge.target,
            {"relation": edge.relation, "document_ids": list(edge.document_ids)},
            rel_type=edge.relation.upper(),
        )

    def query(self, cypher: str) -> Any:
        return self.graph.query(cypher)

    def sync_from_knowledge_graph(self, graph: KnowledgeGraph) -> None:
        for document in graph.all_documents():
            self.upsert_document(document)
        for edge in graph.all_edges():
            self.upsert_edge(edge)


def load_graphqlite_graph(database: str) -> Any:
    ensure_sqlite_extension_loading()
    try:
        from graphqlite import Graph
    except ImportError as exc:  # pragma: no cover - depends on optional runtime package
        raise GraphQLiteUnavailableError(
            "graphqlite is required for GraphQLiteGraphStore. Install requirements.txt or pyproject dependencies."
        ) from exc
    try:
        return Graph(database)
    except RuntimeError as exc:
        raise GraphQLiteRuntimeError(
            "graphqlite is installed, but the current Python sqlite3 runtime cannot load SQLite extensions. "
            "Use a Python build with sqlite3.enable_load_extension support, such as a Homebrew Python on macOS."
        ) from exc


def ensure_sqlite_extension_loading() -> None:
    """Use pysqlite3 when the platform sqlite3 lacks extension loading."""

    import sqlite3

    connection = sqlite3.connect(":memory:")
    try:
        if hasattr(connection, "enable_load_extension"):
            return
    finally:
        connection.close()

    try:
        import pysqlite3
    except ImportError as exc:  # pragma: no cover - dependency/runtime environment specific
        raise GraphQLiteRuntimeError(
            "graphqlite requires sqlite extension loading, but the current sqlite3 runtime does not support it. "
            "Install pysqlite3 or use a Python build with sqlite3.enable_load_extension support."
        ) from exc

    sys.modules["sqlite3"] = pysqlite3


def check_graphqlite_runtime(database: str = ":memory:") -> tuple[bool, str]:
    try:
        graph = load_graphqlite_graph(database)
        graph.upsert_node("teaagent_smoke", {"name": "TeaAgent"}, label="SmokeTest")
        graph.query("MATCH (n:SmokeTest) RETURN n.name")
    except (GraphQLiteUnavailableError, GraphQLiteRuntimeError) as exc:
        return False, str(exc)
    return True, "graphqlite runtime is available"
