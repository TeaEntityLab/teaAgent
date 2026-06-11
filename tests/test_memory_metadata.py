from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from teaagent.memory.catalog import (
    MemoryCatalog,
    MemoryEntry,
    MemoryMeta,
    compute_freshness,
    memory_entry_from_payload,
)


def test_memory_meta_construct_minimal() -> None:
    meta = MemoryMeta(scope='project', owner='run-001')
    assert meta.scope == 'project'
    assert meta.owner == 'run-001'
    assert meta.source_run_id is None
    assert meta.freshness_score == pytest.approx(1.0)
    assert meta.ttl_days == 30
    assert meta.confidence == pytest.approx(0.0)
    assert meta.review_state == 'pending'


def test_memory_meta_construct_full() -> None:
    meta = MemoryMeta(
        scope='personal',
        owner='user-abc',
        source_run_id='run-xyz',
        freshness_score=0.75,
        ttl_days=14,
        confidence=0.9,
        review_state='approved',
    )
    assert meta.scope == 'personal'
    assert meta.owner == 'user-abc'
    assert meta.source_run_id == 'run-xyz'
    assert meta.freshness_score == pytest.approx(0.75)
    assert meta.ttl_days == 14
    assert meta.confidence == pytest.approx(0.9)
    assert meta.review_state == 'approved'


def test_memory_meta_freshness_score_bounds_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryMeta(scope='auto', owner='x', freshness_score=-0.1)
    with pytest.raises(ValueError):
        MemoryMeta(scope='auto', owner='x', freshness_score=1.1)


def test_memory_meta_confidence_bounds_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryMeta(scope='auto', owner='x', confidence=-0.01)
    with pytest.raises(ValueError):
        MemoryMeta(scope='auto', owner='x', confidence=1.01)


def test_memory_meta_invalid_review_state_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryMeta(scope='auto', owner='x', review_state='bogus')


def test_memory_meta_all_review_states_accepted() -> None:
    for state in ('pending', 'approved', 'rejected', 'quarantined', 'promoted'):
        meta = MemoryMeta(scope='auto', owner='x', review_state=state)
        assert meta.review_state == state


def test_memory_meta_to_dict_roundtrip() -> None:
    original = MemoryMeta(
        scope='project',
        owner='run-42',
        source_run_id='run-42',
        freshness_score=0.6,
        ttl_days=7,
        confidence=0.85,
        review_state='quarantined',
    )
    restored = MemoryMeta.from_dict(original.to_dict())
    assert restored.scope == original.scope
    assert restored.owner == original.owner
    assert restored.source_run_id == original.source_run_id
    assert restored.freshness_score == pytest.approx(original.freshness_score)
    assert restored.ttl_days == original.ttl_days
    assert restored.confidence == pytest.approx(original.confidence)
    assert restored.review_state == original.review_state


def test_memory_meta_from_dict_defaults() -> None:
    meta = MemoryMeta.from_dict({})
    assert meta.scope == 'auto'
    assert meta.owner == 'unknown'
    assert meta.review_state == 'pending'


def test_compute_freshness_just_created() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    assert compute_freshness(now_iso, ttl_days=30) == pytest.approx(1.0, abs=0.01)


def test_compute_freshness_half_ttl_elapsed() -> None:
    half_ago = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    score = compute_freshness(half_ago, ttl_days=30)
    assert score == pytest.approx(0.5, abs=0.05)


def test_compute_freshness_at_ttl_boundary() -> None:
    at_ttl = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    score = compute_freshness(at_ttl, ttl_days=30)
    assert score == pytest.approx(0.0, abs=0.01)


def test_compute_freshness_past_ttl() -> None:
    past = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    assert compute_freshness(past, ttl_days=30) == pytest.approx(0.0)


def test_compute_freshness_ttl_none_always_fresh() -> None:
    ancient = '2020-01-01T00:00:00+00:00'
    assert compute_freshness(ancient, ttl_days=None) == pytest.approx(1.0)


def test_compute_freshness_ttl_zero_always_fresh() -> None:
    ancient = '2020-01-01T00:00:00+00:00'
    assert compute_freshness(ancient, ttl_days=0) == pytest.approx(1.0)


def test_compute_freshness_unparseable_timestamp_fallback() -> None:
    assert compute_freshness('not-a-date', ttl_days=30) == pytest.approx(0.5)


def test_memory_entry_without_meta_serializes_cleanly() -> None:
    entry = MemoryEntry(memory_id='mem-1', content='hello', tags=('test',))
    d = entry.to_dict()
    assert 'meta' not in d
    assert d['memory_id'] == 'mem-1'


def test_memory_entry_with_meta_roundtrip() -> None:
    meta = MemoryMeta(
        scope='project',
        owner='run-1',
        freshness_score=0.9,
        confidence=0.7,
    )
    entry = MemoryEntry(
        memory_id='mem-2',
        content='world',
        meta=meta,
    )
    d = entry.to_dict()
    assert 'meta' in d
    assert d['meta']['scope'] == 'project'


def test_memory_entry_from_payload_without_meta() -> None:
    payload = {
        'memory_id': 'mem-3',
        'content': 'bare',
        'tags': ['a'],
        'created_at': '2025-01-01T00:00:00+00:00',
    }
    entry = memory_entry_from_payload(payload)
    assert entry is not None
    assert entry.meta is None


def test_memory_entry_from_payload_with_meta() -> None:
    payload = {
        'memory_id': 'mem-4',
        'content': 'rich',
        'tags': ['b'],
        'created_at': '2025-01-01T00:00:00+00:00',
        'meta': {
            'scope': 'personal',
            'owner': 'u1',
            'freshness_score': 0.5,
            'confidence': 0.3,
            'review_state': 'approved',
        },
    }
    entry = memory_entry_from_payload(payload)
    assert entry is not None
    assert entry.meta.scope == 'personal'
    assert entry.meta.review_state == 'approved'


def test_memory_entry_from_payload_with_malformed_meta_degrades() -> None:
    payload = {
        'memory_id': 'mem-5',
        'content': 'bad-meta',
        'tags': [],
        'created_at': '2025-01-01T00:00:00+00:00',
        'meta': {'freshness_score': 'not-a-number'},
    }
    entry = memory_entry_from_payload(payload)
    assert entry is not None
    assert entry.meta is None


def test_memory_catalog_add_with_meta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        meta = MemoryMeta(
            scope='project',
            owner='run-99',
            freshness_score=0.8,
            confidence=0.6,
            review_state='approved',
        )
        entry = catalog.add('hello', meta=meta)
        assert entry.meta.scope == 'project'
        assert entry.meta.review_state == 'approved'
        assert entry.meta.confidence == pytest.approx(0.6)

        loaded = catalog.show(entry.memory_id)
        assert loaded.meta.scope == 'project'


def test_memory_catalog_add_without_meta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        entry = catalog.add('minimal')
        assert entry.meta is None


def test_memory_catalog_add_quarantined_with_meta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        meta = MemoryMeta(
            scope='auto',
            owner='agent-007',
            review_state='quarantined',
            confidence=0.3,
        )
        entry = catalog.add_quarantined(
            'quarantine test',
            provenance={'reason': 'test'},
            meta=meta,
        )
        assert entry.meta.scope == 'auto'
        assert entry.meta.review_state == 'quarantined'


def test_memory_catalog_set_review_state_existing_meta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        meta = MemoryMeta(
            scope='project',
            owner='run-1',
            review_state='pending',
            confidence=0.5,
        )
        entry = catalog.add('review me', meta=meta)

        updated = catalog.set_review_state(
            entry.memory_id, 'approved', attestation='op:alice'
        )
        assert updated.meta.review_state == 'approved'
        assert updated.meta.scope == 'project'
        assert updated.meta.confidence == 0.5

        loaded = catalog.show(entry.memory_id)
        assert loaded.meta.review_state == 'approved'


def test_memory_catalog_set_review_state_no_existing_meta() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        entry = catalog.add('bare entry')

        updated = catalog.set_review_state(
            entry.memory_id, 'rejected', attestation='op:bob'
        )
        assert updated.meta.review_state == 'rejected'
        assert updated.meta.scope == 'auto'
        assert updated.meta.owner == 'op:bob'


def test_memory_catalog_set_review_state_invalid_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        entry = catalog.add('test')
        with pytest.raises(ValueError):
            catalog.set_review_state(entry.memory_id, 'bogus', attestation='x')


def test_memory_catalog_set_review_state_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        catalog = MemoryCatalog(tmp)
        with pytest.raises(FileNotFoundError):
            catalog.set_review_state('nonexistent', 'approved', attestation='x')


def test_memory_catalog_set_review_state_readonly_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ro = MemoryCatalog(tmp, readonly=True)
        with pytest.raises(RuntimeError):
            ro.set_review_state('any', 'approved', attestation='x')


def test_memory_entry_importable() -> None:
    from teaagent import MemoryEntry  # noqa: F811

    assert callable(getattr(MemoryEntry, 'to_dict', None))
