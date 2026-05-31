from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from teaagent.context_bus import (
    ContextBus,
    ContextBusConfig,
    DeltaCard,
    DeltaType,
)


class TestContextBus:
    """Test suite for ContextBus cross-sandbox Delta sharing."""

    def test_context_bus_initialization(self):
        """Test that context bus initializes with database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            assert bus._workflow_id == 'test-workflow'
            assert bus._db_path == db_path

            bus.close()

    def test_publish_delta(self):
        """Test publishing a Delta card."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            delta = DeltaCard(
                delta_id='delta-1',
                delta_type=DeltaType.CODE_CHANGE,
                source_agent='agent-1',
                content='Changed file foo.py',
            )

            bus.publish_delta(delta)

            count = bus.get_delta_count()
            assert count == 1

            bus.close()

    def test_subscribe_deltas(self):
        """Test subscribing to Delta cards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            delta1 = DeltaCard(
                delta_id='delta-1',
                delta_type=DeltaType.CODE_CHANGE,
                source_agent='agent-1',
                content='Change 1',
            )

            delta2 = DeltaCard(
                delta_id='delta-2',
                delta_type=DeltaType.DISCOVERY,
                source_agent='agent-2',
                content='Discovery 1',
            )

            bus.publish_delta(delta1)
            bus.publish_delta(delta2)

            deltas = bus.subscribe_deltas()

            assert len(deltas) == 2

            bus.close()

    def test_subscribe_deltas_filtered_by_agent(self):
        """Test subscribing to Delta cards filtered by agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            delta1 = DeltaCard(
                delta_id='delta-1',
                delta_type=DeltaType.CODE_CHANGE,
                source_agent='agent-1',
                content='Change 1',
            )

            delta2 = DeltaCard(
                delta_id='delta-2',
                delta_type=DeltaType.DISCOVERY,
                source_agent='agent-2',
                content='Discovery 1',
            )

            bus.publish_delta(delta1)
            bus.publish_delta(delta2)

            deltas = bus.subscribe_deltas(source_agent='agent-1')

            assert len(deltas) == 1
            assert deltas[0].source_agent == 'agent-1'

            bus.close()

    def test_subscribe_deltas_filtered_by_type(self):
        """Test subscribing to Delta cards filtered by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            delta1 = DeltaCard(
                delta_id='delta-1',
                delta_type=DeltaType.CODE_CHANGE,
                source_agent='agent-1',
                content='Change 1',
            )

            delta2 = DeltaCard(
                delta_id='delta-2',
                delta_type=DeltaType.DISCOVERY,
                source_agent='agent-2',
                content='Discovery 1',
            )

            bus.publish_delta(delta1)
            bus.publish_delta(delta2)

            deltas = bus.subscribe_deltas(delta_type=DeltaType.CODE_CHANGE)

            assert len(deltas) == 1
            assert deltas[0].delta_type == DeltaType.CODE_CHANGE

            bus.close()

    def test_clear_deltas(self):
        """Test clearing Delta cards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')

            bus = ContextBus(config)

            delta = DeltaCard(
                delta_id='delta-1',
                delta_type=DeltaType.CODE_CHANGE,
                source_agent='agent-1',
                content='Change 1',
            )

            bus.publish_delta(delta)

            assert bus.get_delta_count() == 1

            bus._clear_deltas()

            assert bus.get_delta_count() == 0

            bus.close()

    def test_cleanup_old_deltas_scoped_to_workflow(self):
        """cleanup_old_deltas must not delete other workflows' cards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            bus_a = ContextBus(
                ContextBusConfig(db_path=db_path, workflow_id='workflow-a')
            )
            bus_b = ContextBus(
                ContextBusConfig(db_path=db_path, workflow_id='workflow-b')
            )
            old_ts = 1.0
            bus_a.publish_delta(
                DeltaCard(
                    delta_id='old-a',
                    delta_type=DeltaType.DISCOVERY,
                    source_agent='agent-1',
                    content='stale',
                    timestamp=old_ts,
                )
            )
            bus_b.publish_delta(
                DeltaCard(
                    delta_id='keep-b',
                    delta_type=DeltaType.DISCOVERY,
                    source_agent='agent-1',
                    content='keep',
                    timestamp=old_ts,
                )
            )
            bus_a._config.max_delta_age_seconds = 0
            bus_a.cleanup_old_deltas()
            assert bus_a.get_delta_count() == 0
            assert bus_b.get_delta_count() == 1
            bus_a.close()
            bus_b.close()

    def test_parallel_publish_from_threads(self):
        """Concurrent publishes use per-thread SQLite connections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')
            bus = ContextBus(config)
            errors: list[Exception] = []

            def publish(i: int) -> None:
                try:
                    bus.publish_delta(
                        DeltaCard(
                            delta_id=f'delta-{i}',
                            delta_type=DeltaType.DISCOVERY,
                            source_agent=f'agent-{i % 3}',
                            content=f'content-{i}',
                        )
                    )
                except Exception as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            threads = [threading.Thread(target=publish, args=(i,)) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            assert not errors
            assert bus.get_delta_count() == 12
            bus.close()

    def test_delta_card_metadata(self):
        """Test DeltaCard with metadata."""
        delta = DeltaCard(
            delta_id='delta-1',
            delta_type=DeltaType.CODE_CHANGE,
            source_agent='agent-1',
            content='Change 1',
            metadata={'file': 'foo.py', 'line': 42},
        )

        assert delta.metadata['file'] == 'foo.py'
        assert delta.metadata['line'] == 42


class FakeRagStore:
    """In-memory RAG store for testing archive_to_rag."""

    def __init__(self) -> None:
        self.documents: list[dict] = []

    def add_document(self, doc: dict) -> None:
        self.documents.append(doc)


class TestArchiveToRag:
    """Tests for archive_to_rag ID-based deletion fix."""

    def test_archive_to_rag_basic(self):
        """Publish a delta, archive, verify count drops to zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')
            bus = ContextBus(config)

            bus.publish_delta(
                DeltaCard(
                    delta_id='delta-1',
                    delta_type=DeltaType.CODE_CHANGE,
                    source_agent='agent-1',
                    content='Change 1',
                )
            )
            assert bus.get_delta_count() == 1

            rag = FakeRagStore()
            bus.archive_to_rag(rag)

            assert bus.get_delta_count() == 0
            assert len(rag.documents) == 1
            assert rag.documents[0]['doc_id'] == 'delta-1'
            bus.close()

    def test_archive_to_rag_with_concurrent_publish(self):
        """Concurrently published delta survives archive (no timestamp collision)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')
            bus = ContextBus(config)

            bus.publish_delta(
                DeltaCard(
                    delta_id='delta-1',
                    delta_type=DeltaType.CODE_CHANGE,
                    source_agent='agent-1',
                    content='Change 1',
                )
            )

            class ConcurrentRagStore:
                def __init__(self, bus):
                    self.bus = bus
                    self.call_count = 0

                def add_document(self, doc):
                    self.call_count += 1
                    if self.call_count == 1:
                        # Simulate a concurrent publish during the RAG archive
                        # window (Phase 2 — no DB lock held).
                        self.bus.publish_delta(
                            DeltaCard(
                                delta_id='concurrent-delta',
                                delta_type=DeltaType.DISCOVERY,
                                source_agent='concurrent',
                                content='Concurrent publish!',
                            )
                        )

            bus.archive_to_rag(ConcurrentRagStore(bus))

            # The concurrently published delta has a different ID, so it
            # should NOT be in archived_ids and must survive deletion.
            assert bus.get_delta_count() == 1
            remaining = bus.subscribe_deltas()
            assert remaining[0].delta_id == 'concurrent-delta'
            bus.close()

    def test_archive_to_rag_rag_store_failure(self):
        """RAG store failure does NOT delete deltas (no data loss)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(db_path=db_path, workflow_id='test-workflow')
            bus = ContextBus(config)

            bus.publish_delta(
                DeltaCard(
                    delta_id='delta-1',
                    delta_type=DeltaType.CODE_CHANGE,
                    source_agent='agent-1',
                    content='Change 1',
                )
            )
            assert bus.get_delta_count() == 1

            class FailingRagStore:
                def add_document(self, doc):  # type: ignore[no-untyped-def]
                    raise RuntimeError('RAG store unavailable')

            bus.archive_to_rag(FailingRagStore())

            # Delta survives because archive failed — no archived_ids → no delete.
            assert bus.get_delta_count() == 1
            bus.close()
