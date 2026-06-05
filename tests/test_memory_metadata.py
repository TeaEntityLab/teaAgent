from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from teaagent.memory.catalog import (
    MemoryCatalog,
    MemoryEntry,
    MemoryMeta,
    compute_freshness,
    memory_entry_from_payload,
)


class MemoryMetaTests(unittest.TestCase):
    def test_construct_minimal(self) -> None:
        meta = MemoryMeta(scope='project', owner='run-001')
        self.assertEqual(meta.scope, 'project')
        self.assertEqual(meta.owner, 'run-001')
        self.assertIsNone(meta.source_run_id)
        self.assertAlmostEqual(meta.freshness_score, 1.0)
        self.assertEqual(meta.ttl_days, 30)
        self.assertAlmostEqual(meta.confidence, 0.0)
        self.assertEqual(meta.review_state, 'pending')

    def test_construct_full(self) -> None:
        meta = MemoryMeta(
            scope='personal',
            owner='user-abc',
            source_run_id='run-xyz',
            freshness_score=0.75,
            ttl_days=14,
            confidence=0.9,
            review_state='approved',
        )
        self.assertEqual(meta.scope, 'personal')
        self.assertEqual(meta.owner, 'user-abc')
        self.assertEqual(meta.source_run_id, 'run-xyz')
        self.assertAlmostEqual(meta.freshness_score, 0.75)
        self.assertEqual(meta.ttl_days, 14)
        self.assertAlmostEqual(meta.confidence, 0.9)
        self.assertEqual(meta.review_state, 'approved')

    def test_freshness_score_bounds_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MemoryMeta(scope='auto', owner='x', freshness_score=-0.1)
        with self.assertRaises(ValueError):
            MemoryMeta(scope='auto', owner='x', freshness_score=1.1)

    def test_confidence_bounds_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MemoryMeta(scope='auto', owner='x', confidence=-0.01)
        with self.assertRaises(ValueError):
            MemoryMeta(scope='auto', owner='x', confidence=1.01)

    def test_invalid_review_state_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MemoryMeta(scope='auto', owner='x', review_state='bogus')

    def test_all_review_states_accepted(self) -> None:
        for state in ('pending', 'approved', 'rejected', 'quarantined', 'promoted'):
            meta = MemoryMeta(scope='auto', owner='x', review_state=state)
            self.assertEqual(meta.review_state, state)

    def test_to_dict_roundtrip(self) -> None:
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
        self.assertEqual(restored.scope, original.scope)
        self.assertEqual(restored.owner, original.owner)
        self.assertEqual(restored.source_run_id, original.source_run_id)
        self.assertAlmostEqual(restored.freshness_score, original.freshness_score)
        self.assertEqual(restored.ttl_days, original.ttl_days)
        self.assertAlmostEqual(restored.confidence, original.confidence)
        self.assertEqual(restored.review_state, original.review_state)

    def test_from_dict_defaults(self) -> None:
        meta = MemoryMeta.from_dict({})
        self.assertEqual(meta.scope, 'auto')
        self.assertEqual(meta.owner, 'unknown')
        self.assertEqual(meta.review_state, 'pending')


class ComputeFreshnessTests(unittest.TestCase):
    def test_just_created(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        self.assertAlmostEqual(compute_freshness(now_iso, ttl_days=30), 1.0, places=2)

    def test_half_ttl_elapsed(self) -> None:
        half_ago = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        score = compute_freshness(half_ago, ttl_days=30)
        self.assertAlmostEqual(score, 0.5, delta=0.05)

    def test_at_ttl_boundary(self) -> None:
        at_ttl = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        score = compute_freshness(at_ttl, ttl_days=30)
        self.assertAlmostEqual(score, 0.0, delta=0.01)

    def test_past_ttl(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        self.assertAlmostEqual(compute_freshness(past, ttl_days=30), 0.0)

    def test_ttl_none_always_fresh(self) -> None:
        ancient = '2020-01-01T00:00:00+00:00'
        self.assertAlmostEqual(compute_freshness(ancient, ttl_days=None), 1.0)

    def test_ttl_zero_always_fresh(self) -> None:
        ancient = '2020-01-01T00:00:00+00:00'
        self.assertAlmostEqual(compute_freshness(ancient, ttl_days=0), 1.0)

    def test_unparseable_timestamp_fallback(self) -> None:
        self.assertAlmostEqual(compute_freshness('not-a-date', ttl_days=30), 0.5)


class MemoryEntryMetaSerializationTests(unittest.TestCase):
    def test_entry_without_meta_serializes_cleanly(self) -> None:
        entry = MemoryEntry(memory_id='mem-1', content='hello', tags=('test',))
        d = entry.to_dict()
        self.assertNotIn('meta', d)
        self.assertEqual(d['memory_id'], 'mem-1')

    def test_entry_with_meta_roundtrip(self) -> None:
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
        self.assertIn('meta', d)
        self.assertEqual(d['meta']['scope'], 'project')

    def test_from_payload_without_meta(self) -> None:
        payload = {
            'memory_id': 'mem-3',
            'content': 'bare',
            'tags': ['a'],
            'created_at': '2025-01-01T00:00:00+00:00',
        }
        entry = memory_entry_from_payload(payload)
        self.assertIsNotNone(entry)
        self.assertIsNone(entry.meta)

    def test_from_payload_with_meta(self) -> None:
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
        self.assertIsNotNone(entry)
        self.assertEqual(entry.meta.scope, 'personal')
        self.assertEqual(entry.meta.review_state, 'approved')

    def test_from_payload_with_malformed_meta_degrades(self) -> None:
        payload = {
            'memory_id': 'mem-5',
            'content': 'bad-meta',
            'tags': [],
            'created_at': '2025-01-01T00:00:00+00:00',
            'meta': {'freshness_score': 'not-a-number'},
        }
        entry = memory_entry_from_payload(payload)
        self.assertIsNotNone(entry)
        self.assertIsNone(entry.meta)


class MemoryCatalogMetaIntegrationTests(unittest.TestCase):
    def test_add_with_meta(self) -> None:
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
            self.assertEqual(entry.meta.scope, 'project')
            self.assertEqual(entry.meta.review_state, 'approved')
            self.assertAlmostEqual(entry.meta.confidence, 0.6)

            loaded = catalog.show(entry.memory_id)
            self.assertEqual(loaded.meta.scope, 'project')

    def test_add_without_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)
            entry = catalog.add('minimal')
            self.assertIsNone(entry.meta)

    def test_add_quarantined_with_meta(self) -> None:
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
            self.assertEqual(entry.meta.scope, 'auto')
            self.assertEqual(entry.meta.review_state, 'quarantined')

    def test_set_review_state_existing_meta(self) -> None:
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
            self.assertEqual(updated.meta.review_state, 'approved')
            self.assertEqual(updated.meta.scope, 'project')
            self.assertEqual(updated.meta.confidence, 0.5)

            loaded = catalog.show(entry.memory_id)
            self.assertEqual(loaded.meta.review_state, 'approved')

    def test_set_review_state_no_existing_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)
            entry = catalog.add('bare entry')

            updated = catalog.set_review_state(
                entry.memory_id, 'rejected', attestation='op:bob'
            )
            self.assertEqual(updated.meta.review_state, 'rejected')
            self.assertEqual(updated.meta.scope, 'auto')
            self.assertEqual(updated.meta.owner, 'op:bob')

    def test_set_review_state_invalid_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)
            entry = catalog.add('test')
            with self.assertRaises(ValueError):
                catalog.set_review_state(entry.memory_id, 'bogus', attestation='x')

    def test_set_review_state_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)
            with self.assertRaises(FileNotFoundError):
                catalog.set_review_state('nonexistent', 'approved', attestation='x')

    def test_set_review_state_readonly_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ro = MemoryCatalog(tmp, readonly=True)
            with self.assertRaises(RuntimeError):
                ro.set_review_state('any', 'approved', attestation='x')


class MemoryEntryImportTests(unittest.TestCase):
    def test_memory_entry_importable(self) -> None:
        from teaagent import MemoryEntry  # noqa: F811

        self.assertTrue(callable(getattr(MemoryEntry, 'to_dict', None)))


if __name__ == '__main__':
    unittest.main()
