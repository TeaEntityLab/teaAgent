from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

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

    def temporal_range_search(
        self,
        query: str,
        *,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        """Search documents within a time range.

        Args:
            query: Search query string.
            start_time: ISO format start time (e.g., '2024-01-01T00:00:00Z').
            end_time: ISO format end time (e.g., '2024-12-31T23:59:59Z').
            source: Optional source filter.
            limit: Maximum number of results.

        Returns:
            List of retrieval results filtered by time range.
        """
        query_terms = set(tokenize(query))
        scored: list[RetrievalResult] = []

        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None

        for document in self.documents:
            if source is not None and document.source != source:
                continue

            doc_time_str = document.metadata.get('created_at')
            if not doc_time_str:
                continue

            try:
                doc_dt = datetime.fromisoformat(doc_time_str)
            except ValueError:
                continue

            if start_dt and doc_dt < start_dt:
                continue
            if end_dt and doc_dt > end_dt:
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


def skill_rag_retrieve(
    query: str,
    retriever: InMemoryRetriever,
    answer_generator: Callable[[str, str], str],
    *,
    prober: Any = None,
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Perform Skill-RAG retrieval with failure-aware adaptation.

    This function integrates the Skill-RAG framework to prevent query-evidence
    misalignment and query drift during multi-turn retrieval by proactively
    detecting retrieval failures and routing to appropriate remediation skills.

    Args:
        query: The user's query.
        retriever: An InMemoryRetriever instance for document retrieval.
        answer_generator: A callable that takes (query, context) and returns an answer.
        prober: Optional SkillRAGProber instance. Defaults to PromptBasedProber.
        max_rounds: Maximum number of retrieval rounds (default: 3).

    Returns:
        A dictionary containing:
            - answer: The final generated answer.
            - context: The retrieved context.
            - rounds: Number of retrieval rounds used.
            - final_state: The final ProberState.
            - skills_used: List of skills applied during retrieval.
    """
    from teaagent.skill_rag import (
        PromptBasedProber,
        SkillRAGEngine,
    )

    if prober is None:
        prober = PromptBasedProber()

    engine = SkillRAGEngine(prober=prober, max_rounds=max_rounds)
    result = engine.run(query, retriever, answer_generator)

    return {
        'answer': result.answer,
        'context': result.context,
        'rounds': result.rounds,
        'final_state': result.final_state.value,
        'skills_used': result.skills_used,
    }
