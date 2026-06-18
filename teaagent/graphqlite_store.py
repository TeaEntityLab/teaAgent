from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
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
    database: str = ':memory:'


class DummyKnowledgeGraph:
    """Mock KnowledgeGraph fallback when sqlite runtime extension loading is unavailable."""

    def upsert_node(self, *args: Any, **kwargs: Any) -> None:
        pass

    def upsert_edge(self, *args: Any, **kwargs: Any) -> None:
        pass

    def query(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []


class GraphQLiteGraphStore:
    """GraphQLite-backed store for Graph RAG entity and relation data."""

    def __init__(
        self,
        config: Optional[GraphQLiteConfig] = None,
        *,
        graph_factory: Optional[GraphFactory] = None,
    ) -> None:
        self.config = config or GraphQLiteConfig()
        try:
            self.graph = (graph_factory or load_graphqlite_graph)(self.config.database)
        except (
            GraphQLiteUnavailableError,
            GraphQLiteRuntimeError,
            sqlite3.Error,
        ) as exc:
            import sys

            print(
                f'[TeaAgent WARNING] GraphQLite runtime is unavailable: {exc}. '
                f'Gracefully degrading to file-level semantic index & hybrid search fallback.',
                file=sys.stderr,
            )
            self.graph = DummyKnowledgeGraph()

    def upsert_document(self, document: Document) -> None:
        self.graph.upsert_node(
            document.doc_id,
            {
                'doc_id': document.doc_id,
                'text': document.text,
                'source': document.source,
                **document.metadata,
            },
            label='Document',
        )

    def upsert_edge(self, edge: GraphEdge) -> None:
        self.graph.upsert_node(edge.source, {'name': edge.source}, label='Entity')
        self.graph.upsert_node(edge.target, {'name': edge.target}, label='Entity')
        self.graph.upsert_edge(
            edge.source,
            edge.target,
            {'relation': edge.relation, 'document_ids': list(edge.document_ids)},
            rel_type=edge.relation.upper(),
        )

    def query(self, cypher: str, params: Optional[dict[str, Any]] = None) -> Any:
        if params is not None:
            return self.graph.query(cypher, params=params)
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
            'graphqlite is required for GraphQLiteGraphStore. Install requirements.txt or pyproject dependencies.'
        ) from exc
    try:
        return Graph(database)
    except (RuntimeError, OSError, sqlite3.Error) as exc:
        raise GraphQLiteRuntimeError(
            'graphqlite is installed, but the current Python sqlite3 runtime cannot load SQLite extensions. '
            'Use a Python build with sqlite3.enable_load_extension support, such as a Homebrew Python on macOS.'
        ) from exc


def ensure_sqlite_extension_loading() -> None:
    """Use pysqlite3 when the platform sqlite3 lacks extension loading."""

    import sqlite3

    connection = sqlite3.connect(':memory:')
    try:
        if hasattr(connection, 'enable_load_extension'):
            return
    finally:
        connection.close()

    try:
        import pysqlite3
    except (
        ImportError
    ) as exc:  # pragma: no cover - dependency/runtime environment specific
        raise GraphQLiteRuntimeError(
            'graphqlite requires sqlite extension loading, but the current sqlite3 runtime does not support it. '
            'Install pysqlite3 or use a Python build with sqlite3.enable_load_extension support.'
        ) from exc

    sys.modules['sqlite3'] = pysqlite3


def _probe_graphqlite_runtime(database: str) -> tuple[bool, str]:
    try:
        graph = load_graphqlite_graph(database)
        graph.upsert_node('teaagent_smoke', {'name': 'TeaAgent'}, label='SmokeTest')
        graph.query('MATCH (n:SmokeTest) RETURN n.name')
    except (GraphQLiteUnavailableError, GraphQLiteRuntimeError) as exc:
        return False, str(exc)
    return True, 'graphqlite runtime is available'


def check_graphqlite_runtime(database: str = ':memory:') -> tuple[bool, str]:
    """Probe the optional native runtime without risking the caller process."""
    probe = (
        'import json, sys; '
        'from teaagent.graphqlite_store import _probe_graphqlite_runtime; '
        'print(json.dumps(_probe_graphqlite_runtime(sys.argv[1])))'
    )
    try:
        result = subprocess.run(
            [sys.executable, '-c', probe, database],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'graphqlite runtime probe failed: {exc}'
    if result.returncode != 0:
        detail = result.stderr.strip() or f'exit code {result.returncode}'
        return False, f'graphqlite runtime probe failed: {detail}'
    try:
        available, message = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return False, f'graphqlite runtime probe returned invalid output: {exc}'
    return bool(available), str(message)
