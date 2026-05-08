from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

TOKEN_RE = re.compile(r'[A-Za-z0-9_]+')


@dataclass(frozen=True)
class Document:
    doc_id: str
    text: str
    source: str = 'default'
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    document: Document
    score: float
    query: str


class InMemoryRetriever:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    def search(
        self, query: str, *, source: Optional[str] = None, limit: int = 5
    ) -> list[RetrievalResult]:
        query_terms = set(tokenize(query))
        scored: list[RetrievalResult] = []
        for document in self.documents:
            if source is not None and document.source != source:
                continue
            terms = set(tokenize(document.text))
            overlap = query_terms & terms
            if overlap:
                scored.append(
                    RetrievalResult(
                        document=document,
                        score=len(overlap) / max(len(query_terms), 1),
                        query=query,
                    )
                )
        return sorted(scored, key=lambda result: result.score, reverse=True)[:limit]


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def decompose_query(query: str) -> list[str]:
    parts = [
        part.strip()
        for part in re.split(
            r'\b(?:and|vs|versus|compare|then)\b|[;。；]', query, flags=re.I
        )
    ]
    return [part for part in parts if part] or [query]


def route_source(query: str) -> str:
    lowered = query.lower()
    if any(word in lowered for word in ('sql', 'table', 'database', 'revenue', 'cost')):
        return 'structured'
    if any(word in lowered for word in ('latest', 'today', 'current', 'news')):
        return 'web'
    return 'semantic'


def reciprocal_rank_fusion(
    result_sets: list[list[RetrievalResult]], *, k: int = 60
) -> list[RetrievalResult]:
    scores: dict[str, float] = defaultdict(float)
    documents: dict[str, RetrievalResult] = {}
    for results in result_sets:
        for rank, result in enumerate(results, start=1):
            scores[result.document.doc_id] += 1 / (k + rank)
            documents[result.document.doc_id] = result
    fused = [
        RetrievalResult(
            document=documents[doc_id].document,
            score=score,
            query=documents[doc_id].query,
        )
        for doc_id, score in scores.items()
    ]
    return sorted(fused, key=lambda result: result.score, reverse=True)


def agentic_retrieve(
    query: str, retriever: InMemoryRetriever, *, limit: int = 5
) -> list[RetrievalResult]:
    result_sets = []
    for subquery in decompose_query(query):
        source = route_source(subquery)
        result_sets.append(retriever.search(subquery, source=source, limit=limit))
    return reciprocal_rank_fusion(result_sets)[:limit]
