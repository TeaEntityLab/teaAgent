"""CPP-P0-003 — Memory write quarantine for agent-created durable project memory."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.chat_agent import _auto_curate_memory
from teaagent.memory.catalog import MemoryCatalog
from teaagent.provenance_gate import (
    PersistenceSubstrate,
    ProvenanceSourceKind,
    evaluate_persistent_write,
)
from teaagent.runner._types import FinalAnswer, RunResult


class ProvenanceGateMemoryQuarantineTests(unittest.TestCase):
    def test_agent_run_memory_returns_quarantine(self) -> None:
        result = evaluate_persistent_write(
            substrate=PersistenceSubstrate.MEMORY,
            payload={'content': 'test memory content', 'tags': ['test']},
            source_kind=ProvenanceSourceKind.AGENT_RUN,
        )
        self.assertEqual(result.action, 'quarantine')
        self.assertIn('agent_created_memory_default_quarantine', result.reason)

    def test_agent_run_non_memory_still_allowed(self) -> None:
        result = evaluate_persistent_write(
            substrate=PersistenceSubstrate.FILESYSTEM,
            payload={'path': '/tmp/test'},
            source_kind=ProvenanceSourceKind.AGENT_RUN,
        )
        self.assertEqual(result.action, 'allow')

    def test_local_memory_still_allowed(self) -> None:
        result = evaluate_persistent_write(
            substrate=PersistenceSubstrate.MEMORY,
            payload={'content': 'test memory content', 'tags': ['test']},
            source_kind=ProvenanceSourceKind.LOCAL,
        )
        self.assertEqual(result.action, 'allow')

    def test_provenance_gate_emits_audit_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-001'

            evaluate_persistent_write(
                substrate=PersistenceSubstrate.MEMORY,
                payload={'content': 'audit test', 'tags': ['test']},
                source_kind=ProvenanceSourceKind.AGENT_RUN,
                run_id=run_id,
                audit_logger=audit,
            )

            self.assertTrue(log_path.exists())
            self.assertTrue(len(audit.events) >= 1)

            events = audit.events
            quarantine_events = [
                e for e in events if e.event_type == 'memory_write_quarantined'
            ]
            self.assertEqual(len(quarantine_events), 1)
            self.assertEqual(quarantine_events[0].run_id, run_id)
            self.assertIn('content_digest', quarantine_events[0].payload)


class AutoCurateMemoryQuarantineTests(unittest.TestCase):
    def test_auto_curate_memory_writes_to_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / '.teaagent' / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-002'

            result = RunResult(
                run_id=run_id,
                final_answer=FinalAnswer(content='Task completed successfully.'),
                iterations=3,
                tool_calls=1,
                status='completed',
            )

            _auto_curate_memory(
                root=root,
                task='Test task for memory quarantine',
                result=result,
                audit_events=[],
                run_id=run_id,
                audit=audit,
            )

            catalog = MemoryCatalog(root)
            main_entries = catalog.list(limit=10)
            quarantined_entries = catalog.list_quarantined(limit=10)

            self.assertEqual(
                len(main_entries),
                0,
                'Auto-curated memory should NOT go to main catalog',
            )
            self.assertGreater(
                len(quarantined_entries),
                0,
                'Auto-curated memory should go to quarantine',
            )

            entry = quarantined_entries[0]
            self.assertIn('auto-curated', entry.tags)
            self.assertIn('run-summary', entry.tags)
            self.assertEqual(entry.run_id, run_id)

    def test_auto_curate_skips_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / '.teaagent' / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-003'

            result = RunResult(
                run_id=run_id,
                final_answer=FinalAnswer(content='Same outcome.'),
                iterations=1,
                tool_calls=0,
                status='completed',
            )

            _auto_curate_memory(
                root=root,
                task='Duplicate test',
                result=result,
                audit_events=[],
                run_id=run_id,
                audit=audit,
            )

            _auto_curate_memory(
                root=root,
                task='Duplicate test',
                result=result,
                audit_events=[],
                run_id=run_id + '-2',
                audit=audit,
            )

            quarantined_entries = MemoryCatalog(root).list_quarantined(limit=10)
            self.assertEqual(
                len(quarantined_entries),
                1,
                'Duplicate auto-curated summary should be skipped',
            )

    def test_auto_curate_skips_incomplete_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / '.teaagent' / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-failed'

            result = RunResult(
                run_id=run_id,
                final_answer=None,
                iterations=1,
                tool_calls=0,
                status='error',
                error_message='Something went wrong',
            )

            _auto_curate_memory(
                root=root,
                task='Failed task',
                result=result,
                audit_events=[],
                run_id=run_id,
                audit=audit,
            )

            catalog = MemoryCatalog(root)
            self.assertEqual(len(catalog.list(limit=10)), 0)
            self.assertEqual(len(catalog.list_quarantined(limit=10)), 0)


class AuditEventEmissionTests(unittest.TestCase):
    def test_catalog_add_quarantined_emits_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / '.teaagent' / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-004'

            catalog = MemoryCatalog(root)
            catalog.add_quarantined(
                'Audit event test content',
                tags=('test',),
                provenance={
                    'source_kind': 'agent_run',
                    'run_id': run_id,
                    'reason': 'test_quarantine_reason',
                },
                run_id=run_id,
                audit_logger=audit,
            )

            quarantine_events = [
                e for e in audit.events if e.event_type == 'memory_write_quarantined'
            ]
            self.assertEqual(len(quarantine_events), 1)
            self.assertEqual(quarantine_events[0].run_id, run_id)
            self.assertEqual(
                quarantine_events[0].payload.get('quarantine_reason'),
                'test_quarantine_reason',
            )

    def test_catalog_promote_quarantined_emits_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / '.teaagent' / 'audit.jsonl'
            audit = AuditLogger(path=log_path)
            run_id = 'test-run-005'

            catalog = MemoryCatalog(root)
            entry = catalog.add_quarantined(
                'Content to promote',
                tags=('to-promote',),
                provenance={'source_kind': 'agent_run', 'reason': 'test'},
                run_id=run_id,
            )

            catalog.promote_quarantined(
                entry.memory_id,
                attestation='operator-approved',
                audit_logger=audit,
                run_id=run_id,
            )

            promote_events = [
                e for e in audit.events if e.event_type == 'memory_write_promoted'
            ]
            self.assertEqual(len(promote_events), 1)
            self.assertEqual(promote_events[0].run_id, run_id)
            self.assertEqual(
                promote_events[0].payload.get('memory_id'),
                entry.memory_id,
            )
            self.assertEqual(
                promote_events[0].payload.get('attestation'),
                'operator-approved',
            )

            main_entries = catalog.list(limit=10)
            self.assertEqual(len(main_entries), 1)
            self.assertEqual(main_entries[0].memory_id, entry.memory_id)


class QuarantinePromoteFlowTests(unittest.TestCase):
    def test_full_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = MemoryCatalog(root)
            run_id = 'full-flow-run'

            entry = catalog.add_quarantined(
                'Memory that needs review',
                tags=('review-needed',),
                provenance={
                    'source_kind': 'agent_run',
                    'run_id': run_id,
                    'reason': 'auto_curated_agent_memory',
                    'content_digest': 'sha256:abc123',
                },
                run_id=run_id,
            )

            self.assertEqual(len(catalog.list(limit=10)), 0)
            quarantined = catalog.list_quarantined(limit=10)
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].memory_id, entry.memory_id)

            promoted = catalog.promote_quarantined(
                entry.memory_id,
                attestation='human-reviewed-and-approved',
            )

            self.assertEqual(promoted.memory_id, entry.memory_id)
            self.assertEqual(promoted.content, 'Memory that needs review')

            main_entries = catalog.list(limit=10)
            self.assertEqual(len(main_entries), 1)
            self.assertEqual(main_entries[0].content, 'Memory that needs review')

            self.assertEqual(len(catalog.list_quarantined(limit=10)), 0)

    def test_promote_nonexistent_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(Path(tmp))
            with self.assertRaises(FileNotFoundError):
                catalog.promote_quarantined(
                    'nonexistent-id',
                    attestation='does-not-matter',
                )
