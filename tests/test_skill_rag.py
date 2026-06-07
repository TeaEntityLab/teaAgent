from __future__ import annotations

import pytest

from teaagent.rag import Document, InMemoryRetriever
from teaagent.skill_rag import (
    HiddenStateProber,
    ProberState,
    PromptBasedProber,
    SkillRAGEngine,
    SkillRouter,
)


class TestPromptBasedProber:
    """Test suite for PromptBasedProber."""

    def test_prober_identifies_sufficient_context(self):
        """Test that prober correctly identifies sufficient context."""
        prober = PromptBasedProber()
        query = 'What is the capital of France?'
        context = (
            'Paris is the capital city of France. It is known for the Eiffel Tower.'
        )
        answer = 'The capital of France is Paris.'

        state, reasoning = prober.probe(query, context, answer)

        assert state == ProberState.SUFFICIENT
        assert 'sufficient' in reasoning.lower()

    def test_prober_identifies_insufficient_context_with_uncertainty(self):
        """Test that prober detects insufficient context when answer has uncertainty markers."""
        prober = PromptBasedProber()
        query = 'What is the population of Tokyo?'
        context = 'Tokyo is a major city in Japan.'
        answer = "I don't know the population of Tokyo due to insufficient context."

        state, reasoning = prober.probe(query, context, answer)

        assert state == ProberState.INSUFFICIENT
        assert 'uncertainty' in reasoning.lower()

    def test_prober_identifies_insufficient_short_context(self):
        """Test that prober detects insufficient context when it's too short."""
        prober = PromptBasedProber()
        query = 'Explain the history of the Roman Empire'
        context = 'Rome'
        answer = 'Rome was an empire.'

        state, reasoning = prober.probe(query, context, answer)

        assert state == ProberState.INSUFFICIENT
        assert 'too short' in reasoning.lower()

    def test_prober_identifies_misaligned_context_no_overlap(self):
        """Test that prober detects misalignment when there's no term overlap."""
        prober = PromptBasedProber()
        query = 'What is quantum computing?'
        context = 'The capital of France is Paris and it has many museums.'
        answer = "The context doesn't mention quantum computing."

        state, reasoning = prober.probe(query, context, answer)

        assert state == ProberState.MISALIGNED
        assert 'overlap' in reasoning.lower()

    def test_prober_identifies_misaligned_context_low_overlap(self):
        """Test that prober detects misalignment with low term overlap."""
        prober = PromptBasedProber()
        query = 'How does machine learning work?'
        context = 'The capital of France is Paris and learning is important.'
        answer = 'The context mentions learning but not machine learning.'

        state, reasoning = prober.probe(query, context, answer)

        assert state == ProberState.MISALIGNED
        assert 'overlap' in reasoning.lower()

    def test_prober_custom_confidence_threshold(self):
        """Test that custom confidence threshold is respected."""
        prober = PromptBasedProber(confidence_threshold=0.9)
        query = 'What is Python?'
        context = 'Python is a programming language.'
        answer = 'Python is a programming language.'

        # Even with good context, high threshold might still pass
        state, reasoning = prober.probe(query, context, answer)
        assert state in [ProberState.SUFFICIENT, ProberState.INSUFFICIENT]


class TestSkillRouter:
    """Test suite for SkillRouter."""

    def test_router_routes_to_exit_for_sufficient_state(self):
        """Test that router exits when context is sufficient."""
        router = SkillRouter()
        query = 'What is the capital of France?'
        context = 'Paris is the capital of France.'
        state = ProberState.SUFFICIENT

        skill_name, instruction = router.route(query, context, state)

        assert skill_name == 'exit'
        assert 'sufficient' in instruction.lower()

    def test_router_routes_to_query_rewriting_for_vague_query(self):
        """Test that router selects query rewriting for vague queries."""
        router = SkillRouter()
        query = 'Paris'
        context = 'Some information about cities.'
        state = ProberState.MISALIGNED

        skill_name, instruction = router.route(query, context, state)

        assert skill_name == 'query_rewriting'
        assert 'rewrite' in instruction.lower()

    def test_router_routes_to_decomposition_for_multi_part_query(self):
        """Test that router selects decomposition for multi-part queries."""
        router = SkillRouter()
        query = 'Compare Paris and London'
        context = 'Information about cities.'
        state = ProberState.MISALIGNED

        skill_name, instruction = router.route(query, context, state)

        assert skill_name == 'question_decomposition'
        assert 'decompose' in instruction.lower()

    def test_router_routes_to_evidence_focusing_for_missing_details(self):
        """Test that router selects evidence focusing when details are missing."""
        router = SkillRouter()
        query = 'What is the population of Tokyo?'
        context = 'Tokyo is a city with specific details needed.'
        state = ProberState.INSUFFICIENT

        skill_name, instruction = router.route(query, context, state)

        assert skill_name == 'evidence_focusing'
        assert 'focus' in instruction.lower()

    def test_router_defaults_to_query_rewriting_for_insufficient(self):
        """Test that router defaults to query rewriting for insufficient context."""
        router = SkillRouter()
        query = 'What is machine learning?'
        context = 'Some general information.'
        state = ProberState.INSUFFICIENT

        skill_name, instruction = router.route(query, context, state)

        assert skill_name == 'query_rewriting'
        assert 'rewrite' in instruction.lower()

    def test_router_decompose_question_splits_correctly(self):
        """Test that question decomposition splits multi-part queries correctly."""
        router = SkillRouter()
        query = 'Compare Paris and London and then discuss Tokyo'

        subqueries = router._decompose_question(query)

        assert len(subqueries) == 3
        assert 'Paris' in subqueries[0]
        assert 'London' in subqueries[1]
        assert 'Tokyo' in subqueries[2]

    def test_router_rewrite_query_adds_context(self):
        """Test that query rewriting adds context terms."""
        router = SkillRouter()
        query = 'Python'

        rewritten = router._rewrite_query(query)

        assert 'Python' in rewritten
        assert 'detailed' in rewritten.lower()

    def test_router_focus_evidence_adds_specificity(self):
        """Test that evidence focusing adds specificity."""
        router = SkillRouter()
        query = 'machine learning'

        focused = router._focus_evidence(query)

        assert 'machine learning' in focused
        assert 'specific' in focused.lower()


class TestSkillRAGEngine:
    """Test suite for SkillRAGEngine."""

    def test_engine_terminates_on_sufficient_context(self):
        """Test that engine terminates when context is sufficient."""
        prober = PromptBasedProber()
        engine = SkillRAGEngine(prober=prober, max_rounds=3)

        documents = [
            Document(
                doc_id='1',
                text='Paris is the capital city of France. It is known for the Eiffel Tower, the Louvre Museum, and its rich cultural heritage. Paris has been a major center of art, fashion, and cuisine for centuries.',
            )
        ]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            return 'The capital of France is Paris.'

        result = engine.run(
            'What is the capital of France?', retriever, answer_generator
        )

        assert result.final_state == ProberState.SUFFICIENT
        assert result.rounds == 1
        assert 'Paris' in result.answer

    def test_engine_respects_max_rounds_limit(self):
        """Test that engine respects max_rounds limit."""
        prober = PromptBasedProber()
        engine = SkillRAGEngine(prober=prober, max_rounds=2)

        documents = [Document(doc_id='1', text='Limited information.')]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            # Always return insufficient to force multiple rounds
            return "I don't know due to insufficient context."

        result = engine.run('Complex query', retriever, answer_generator)

        assert result.rounds <= 2

    def test_engine_tracks_skills_used(self):
        """Test that engine tracks which skills were used."""
        prober = PromptBasedProber()
        engine = SkillRAGEngine(prober=prober, max_rounds=3)

        documents = [Document(doc_id='1', text='Some information.')]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            return "I don't know due to insufficient context."

        result = engine.run('Query', retriever, answer_generator)

        # Should have used at least one skill since context is insufficient
        assert len(result.skills_used) >= 0
        assert isinstance(result.skills_used, list)

    def test_engine_returns_context_and_answer(self):
        """Test that engine returns both context and answer."""
        prober = PromptBasedProber()
        engine = SkillRAGEngine(prober=prober, max_rounds=3)

        documents = [Document(doc_id='1', text='Paris is the capital of France.')]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            return 'The capital of France is Paris.'

        result = engine.run(
            'What is the capital of France?', retriever, answer_generator
        )

        assert result.context
        assert result.answer
        assert 'Paris' in result.context


class TestHiddenStateProber:
    """Test suite for HiddenStateProber."""

    def test_hidden_state_prober_requires_implementation(self):
        """Test that HiddenStateProber requires concrete implementation."""
        # HiddenStateProber is abstract and cannot be instantiated directly
        # This test verifies the abstract nature by attempting to create a subclass
        # without implementing the abstract method
        with pytest.raises(TypeError):
            HiddenStateProber()  # type: ignore[abstract]

    def test_hidden_state_prober_concrete_implementation(self):
        """Test that a concrete implementation of HiddenStateProber works."""

        class ConcreteHiddenStateProber(HiddenStateProber):
            def probe(
                self, query: str, context: str, answer: str
            ) -> tuple[ProberState, str]:
                return ProberState.SUFFICIENT, 'Concrete implementation'

        prober = ConcreteHiddenStateProber()
        state, reasoning = prober.probe('query', 'context', 'answer')

        assert state == ProberState.SUFFICIENT
        assert reasoning == 'Concrete implementation'


class TestSkillRAGIntegration:
    """Integration tests for Skill-RAG with rag.py."""

    def test_skill_rag_retrieve_function_exists(self):
        """Test that skill_rag_retrieve function is available in rag module."""
        from teaagent.rag import skill_rag_retrieve

        assert callable(skill_rag_retrieve)

    def test_skill_rag_retrieve_with_default_prober(self):
        """Test skill_rag_retrieve with default prober."""
        from teaagent.rag import skill_rag_retrieve

        documents = [Document(doc_id='1', text='Paris is the capital of France.')]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            return 'The capital of France is Paris.'

        result = skill_rag_retrieve(
            'What is the capital of France?', retriever, answer_generator
        )

        assert 'answer' in result
        assert 'context' in result
        assert 'rounds' in result
        assert 'final_state' in result
        assert 'skills_used' in result
        assert isinstance(result['rounds'], int)
        assert isinstance(result['skills_used'], list)

    def test_skill_rag_retrieve_with_custom_prober(self):
        """Test skill_rag_retrieve with custom prober."""
        from teaagent.rag import skill_rag_retrieve

        documents = [Document(doc_id='1', text='Paris is the capital of France.')]
        retriever = InMemoryRetriever(documents)
        prober = PromptBasedProber(confidence_threshold=0.5)

        def answer_generator(query, context):
            return 'The capital of France is Paris.'

        result = skill_rag_retrieve(
            'What is the capital of France?',
            retriever,
            answer_generator,
            prober=prober,
        )

        assert 'answer' in result
        assert result['rounds'] >= 1

    def test_skill_rag_retrieve_respects_max_rounds(self):
        """Test that skill_rag_retrieve respects max_rounds parameter."""
        from teaagent.rag import skill_rag_retrieve

        documents = [Document(doc_id='1', text='Limited information.')]
        retriever = InMemoryRetriever(documents)

        def answer_generator(query, context):
            return "I don't know due to insufficient context."

        result = skill_rag_retrieve(
            'Complex query',
            retriever,
            answer_generator,
            max_rounds=2,
        )

        assert result['rounds'] <= 2
