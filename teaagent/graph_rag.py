from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from teaagent.rag import Document, RetrievalResult, tokenize


@dataclass(frozen=True)
class GraphEdge:
    source: str
    relation: str
    target: str
    document_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GraphPath:
    nodes: tuple[str, ...]
    relations: tuple[str, ...]
    document_ids: tuple[str, ...]


class KnowledgeGraph:
    def __init__(self) -> None:
        self._edges: dict[str, list[GraphEdge]] = defaultdict(list)
        self._documents: dict[str, Document] = {}

    def add_document(self, document: Document) -> None:
        self._documents[document.doc_id] = document

    def add_edge(self, edge: GraphEdge) -> None:
        self._edges[edge.source].append(edge)

    def neighbors(self, node: str) -> list[GraphEdge]:
        return list(self._edges.get(node, []))

    def traverse(self, start: str, *, max_depth: int = 2) -> list[GraphPath]:
        paths: list[GraphPath] = []
        queue = deque([(start, (start,), tuple(), tuple(), 0)])
        while queue:
            node, nodes, relations, doc_ids, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self.neighbors(node):
                next_nodes = nodes + (edge.target,)
                next_relations = relations + (edge.relation,)
                next_doc_ids = doc_ids + edge.document_ids
                path = GraphPath(
                    nodes=next_nodes,
                    relations=next_relations,
                    document_ids=dedupe(next_doc_ids),
                )
                paths.append(path)
                queue.append((edge.target, next_nodes, next_relations, next_doc_ids, depth + 1))
        return paths

    def documents_for(self, document_ids: tuple[str, ...]) -> list[Document]:
        return [self._documents[doc_id] for doc_id in document_ids if doc_id in self._documents]

    def all_documents(self) -> list[Document]:
        return list(self._documents.values())

    def all_edges(self) -> list[GraphEdge]:
        return [edge for edges in self._edges.values() for edge in edges]


def dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def graph_retrieve(query: str, graph: KnowledgeGraph, *, max_depth: int = 2, limit: int = 5) -> list[RetrievalResult]:
    query_terms = set(tokenize(query))
    scored: dict[str, RetrievalResult] = {}
    for term in query_terms:
        for path in graph.traverse(term, max_depth=max_depth):
            path_terms = set(tokenize(" ".join(path.nodes + path.relations)))
            score = len(query_terms & path_terms) / max(len(query_terms), 1)
            for document in graph.documents_for(path.document_ids):
                existing = scored.get(document.doc_id)
                if existing is None or score > existing.score:
                    scored[document.doc_id] = RetrievalResult(document=document, score=score, query=query)
    return sorted(scored.values(), key=lambda result: result.score, reverse=True)[:limit]
