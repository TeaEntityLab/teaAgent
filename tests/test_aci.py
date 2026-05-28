"""Tests for ACI (Anticipatory Context Injection) with timeout protection."""

import pytest

from teaagent.prompt import run_aci_injector_sync
from teaagent.rag import Document, InMemoryRetriever


@pytest.fixture
def sample_retriever():
    """Create a sample retriever with test documents."""
    documents = [
        Document(
            doc_id='doc1',
            text='Authentication refactoring involves updating JWT tokens',
            source='semantic',
            metadata={'created_at': '2024-01-01T00:00:00Z'},
        ),
        Document(
            doc_id='doc2',
            text='Database schema changes require migration scripts',
            source='structured',
            metadata={'created_at': '2024-01-02T00:00:00Z'},
        ),
    ]
    return InMemoryRetriever(documents)


def test_aci_sync_wrapper(sample_retriever, tmp_path):
    """Test synchronous wrapper for ACI injector."""
    cache_db = str(tmp_path / 'cache.db')

    result = run_aci_injector_sync(
        'test task', sample_retriever, cache_db, timeout_ms=1500
    )

    assert isinstance(result, str)


def test_aci_with_retriever(sample_retriever, tmp_path):
    """Test ACI with retriever."""
    cache_db = str(tmp_path / 'cache.db')

    result = run_aci_injector_sync(
        'authentication', sample_retriever, cache_db, timeout_ms=2000
    )

    assert isinstance(result, str)


def test_aci_empty_retriever(tmp_path):
    """Test ACI with empty retriever."""
    empty_retriever = InMemoryRetriever([])
    cache_db = str(tmp_path / 'cache.db')

    result = run_aci_injector_sync('test task', empty_retriever, cache_db)

    assert isinstance(result, str)
