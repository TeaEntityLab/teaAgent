"""Acceptance test for Skills Marketplace / Community Hub.

Verifies: MarketplaceRegistry publish/search/list/remove, MarketplaceClient.
"""

from __future__ import annotations

import tempfile

from teaagent.marketplace import MarketplaceRegistry, MarketplaceClient


def test_marketplace_publish_and_search() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = MarketplaceRegistry(tmp)
        entry = registry.publish(
            name='code-review',
            description='Reviews pull requests for code quality',
            version='1.0.0',
            author='teaagent',
            tags=['review', 'code-quality'],
        )
        assert entry.name == 'code-review'
        assert entry.author == 'teaagent'
        assert 'review' in entry.tags

        results = registry.search('code-review')
        assert any(e.name == 'code-review' for e in results)

        results_tag = registry.search(tag='review')
        assert any(e.name == 'code-review' for e in results_tag)


def test_marketplace_list_and_remove() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = MarketplaceRegistry(tmp)
        registry.publish(name='skill-a', description='first')
        registry.publish(name='skill-b', description='second')

        entries = registry.list()
        assert len(entries) == 2
        assert registry.get('skill-a') is not None

        registry.remove(entries[0].entry_id)
        assert len(registry.list()) == 1


def test_marketplace_get_by_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = MarketplaceRegistry(tmp)
        registry.publish(name='finder', description='find me')

        found = registry.get('finder')
        assert found is not None
        assert found.name == 'finder'

        missing = registry.get('nope')
        assert missing is None


def test_marketplace_client_init() -> None:
    client = MarketplaceClient()
    assert client is not None

    client_custom = MarketplaceClient('https://example.com/api')
    assert client_custom is not None


def test_marketplace_client_fetch_no_network() -> None:
    client = MarketplaceClient('https://nonexistent-registry.example/api')
    results = client.fetch(query='test')
    assert results == [], 'should return empty list on network failure'
