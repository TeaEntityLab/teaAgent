from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol


class RetrieverProtocol(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[Any]: ...


class ProberState(Enum):
    """Represents the state of retrieved context sufficiency."""

    SUFFICIENT = 'sufficient'
    INSUFFICIENT = 'insufficient'
    MISALIGNED = 'misaligned'


@dataclass
class SkillRAGResult:
    """Result from a Skill-RAG retrieval operation."""

    answer: str
    context: str
    rounds: int
    final_state: ProberState
    skills_used: list[str]


class SkillRAGProber(ABC):
    """Abstract base class for probing retrieved context sufficiency."""

    @abstractmethod
    def probe(self, query: str, context: str, answer: str) -> tuple[ProberState, str]:
        """Probe whether the retrieved context is sufficient for answering the query.

        Args:
            query: The original user query.
            context: The retrieved context/documents.
            answer: The generated answer based on context.

        Returns:
            A tuple of (ProberState, reasoning) where reasoning explains the state.
        """
        pass


class PromptBasedProber(SkillRAGProber):
    """Prompt-based prober using self-evaluation for API compatibility."""

    def __init__(self, confidence_threshold: float = 0.7):
        """Initialize the prompt-based prober.

        Args:
            confidence_threshold: Minimum confidence level to consider context sufficient.
        """
        self.confidence_threshold = confidence_threshold

    def probe(self, query: str, context: str, answer: str) -> tuple[ProberState, str]:
        """Probe context sufficiency using heuristic analysis.

        This implementation uses simple heuristics for API compatibility.
        In production, this would call an LLM for self-evaluation.

        Args:
            query: The original user query.
            context: The retrieved context/documents.
            answer: The generated answer based on context.

        Returns:
            A tuple of (ProberState, reasoning).
        """
        # Heuristic: Check if answer contains uncertainty markers
        uncertainty_markers = [
            "i don't know",
            'not enough information',
            'cannot determine',
            'insufficient context',
            'unclear',
            'maybe',
        ]
        answer_lower = answer.lower()
        has_uncertainty = any(marker in answer_lower for marker in uncertainty_markers)

        # Heuristic: Check if answer mentions missing information
        if has_uncertainty:
            return (
                ProberState.INSUFFICIENT,
                'Answer contains uncertainty markers suggesting insufficient context.',
            )

        # Heuristic: Check if context is very short
        if len(context) < 50:
            return (
                ProberState.INSUFFICIENT,
                'Context is too short to provide a comprehensive answer.',
            )

        # Heuristic: Check for query-context alignment
        query_terms = set(query.lower().split())
        context_terms = set(context.lower().split())
        overlap = len(query_terms & context_terms)

        if overlap == 0:
            return (
                ProberState.MISALIGNED,
                'No term overlap between query and context suggests misalignment.',
            )

        if overlap < len(query_terms) * 0.3:
            return (
                ProberState.MISALIGNED,
                'Low term overlap between query and context suggests partial misalignment.',
            )

        return (
            ProberState.SUFFICIENT,
            'Context appears sufficient based on heuristic analysis.',
        )


class HiddenStateProber(SkillRAGProber):
    """Abstract hook for hidden-state based probing (local models only).

    This class provides a standard interface for tensor-based gating when
    TeaAgent is running local models (e.g., via PyTorch/Transformers or llama.cpp
    if layer outputs are exposed).
    """

    @abstractmethod
    def probe(self, query: str, context: str, answer: str) -> tuple[ProberState, str]:
        """Probe using raw hidden states from the model.

        This method should be overridden with actual hidden-state extraction
        and classification logic for local model setups.

        Args:
            query: The original user query.
            context: The retrieved context/documents.
            answer: The generated answer based on context.

        Returns:
            A tuple of (ProberState, reasoning).
        """
        raise NotImplementedError(
            'HiddenStateProber requires implementation for local model setups.'
        )


class SkillRouter:
    """Routes retrieval failures to appropriate skills based on failure type."""

    def __init__(self) -> None:
        """Initialize the skill router."""
        self._skills = {
            'query_rewriting': self._rewrite_query,
            'question_decomposition': self._decompose_question,
            'evidence_focusing': self._focus_evidence,
            'exit': self._exit,
        }

    def route(self, query: str, context: str, state: ProberState) -> tuple[str, str]:
        """Route to the appropriate skill based on failure analysis.

        Args:
            query: The current query.
            context: The retrieved context.
            state: The prober state indicating the type of failure.

        Returns:
            A tuple of (skill_name, transformed_query_or_instruction).
        """
        if state == ProberState.SUFFICIENT:
            return 'exit', 'Context is sufficient, exiting retrieval loop.'

        if state == ProberState.MISALIGNED:
            # Check if query is vague or needs reformulation
            if len(query.split()) < 3:
                return (
                    'query_rewriting',
                    f'Rewrite the query to be more specific: {query}',
                )
            # Check if query has multiple components
            if any(
                word in query.lower()
                for word in ['and', 'vs', 'versus', 'compare', 'then']
            ):
                return (
                    'question_decomposition',
                    f'Decompose the multi-part query: {query}',
                )
            # Default to evidence focusing for misalignment
            return (
                'evidence_focusing',
                f'Focus on missing semantic slots in context for: {query}',
            )

        # INSUFFICIENT state
        # Check if answer suggests missing specific information
        if 'specific' in context.lower() or 'detail' in context.lower():
            return (
                'evidence_focusing',
                f'Focus on specific details missing from context for: {query}',
            )

        # Default to query rewriting for insufficient context
        return (
            'query_rewriting',
            f'Rewrite query to retrieve more relevant context: {query}',
        )

    def _rewrite_query(self, query: str) -> str:
        """Rewrite the query for better retrieval.

        Args:
            query: The original query.

        Returns:
            A rewritten query.
        """
        # Simple heuristic: add context terms
        return f'{query} detailed information'

    def _decompose_question(self, query: str) -> list[str]:
        """Decompose a multi-part question into sub-questions.

        Args:
            query: The original multi-part query.

        Returns:
            A list of sub-queries.
        """
        import re

        parts = [
            part.strip()
            for part in re.split(
                r'\b(?:and|vs|versus|compare|then)\b|[;。；]', query, flags=re.I
            )
        ]
        return [part for part in parts if part] or [query]

    def _focus_evidence(self, query: str) -> str:
        """Generate a focused query for missing evidence.

        Args:
            query: The original query.

        Returns:
            A focused query targeting missing information.
        """
        return f'specific details about {query}'

    def _exit(self, query: str) -> str:
        """Exit the retrieval loop.

        Args:
            query: The original query.

        Returns:
            Exit instruction.
        """
        return 'exit'


class SkillRAGEngine:
    """Main coordinator for Skill-RAG retrieval with failure-aware adaptation."""

    def __init__(
        self,
        prober: SkillRAGProber,
        max_rounds: int = 3,
    ):
        """Initialize the Skill-RAG engine.

        Args:
            prober: The prober instance to use for context evaluation.
            max_rounds: Maximum number of retrieval rounds to prevent infinite loops.
        """
        self.prober = prober
        self.max_rounds = max_rounds
        self.router = SkillRouter()

    def run(
        self,
        query: str,
        retriever: RetrieverProtocol,
        answer_generator: Callable[[str, str], str],
    ) -> SkillRAGResult:
        """Run the Skill-RAG retrieval loop.

        Args:
            query: The user's query.
            retriever: A retriever object with a search(query) method.
            answer_generator: A callable that generates answers from (query, context).

        Returns:
            A SkillRAGResult containing the final answer and metadata.
        """
        current_query = query
        context = ''
        skills_used: list[str] = []
        rounds = 0

        while rounds < self.max_rounds:
            rounds += 1

            # Retrieve context
            results = retriever.search(current_query, limit=5)
            context = '\n'.join([result.document.text for result in results if results])

            # Generate answer
            answer = answer_generator(current_query, context)

            # Probe context sufficiency
            state, reasoning = self.prober.probe(current_query, context, answer)

            # If sufficient, return the result
            if state == ProberState.SUFFICIENT:
                return SkillRAGResult(
                    answer=answer,
                    context=context,
                    rounds=rounds,
                    final_state=state,
                    skills_used=skills_used,
                )

            # Route to appropriate skill
            skill_name, instruction = self.router.route(current_query, context, state)
            skills_used.append(skill_name)

            # Execute skill
            if skill_name == 'exit':
                return SkillRAGResult(
                    answer=answer,
                    context=context,
                    rounds=rounds,
                    final_state=state,
                    skills_used=skills_used,
                )

            if skill_name == 'query_rewriting':
                current_query = self.router._rewrite_query(current_query)
            elif skill_name == 'question_decomposition':
                subqueries = self.router._decompose_question(current_query)
                # Use the first subquery for simplicity
                current_query = subqueries[0] if subqueries else current_query
            elif skill_name == 'evidence_focusing':
                current_query = self.router._focus_evidence(current_query)

        # Max rounds reached, return current best result
        return SkillRAGResult(
            answer=answer,
            context=context,
            rounds=rounds,
            final_state=state,
            skills_used=skills_used,
        )
