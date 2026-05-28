from __future__ import annotations

import tempfile
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
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

            bus = ContextBus(config)

            assert bus._workflow_id == 'test-workflow'
            assert bus._db_path == db_path

            bus.close()

    def test_publish_delta(self):
        """Test publishing a Delta card."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'context_bus.db'
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

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
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

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
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

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
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

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
            config = ContextBusConfig(
                db_path=db_path, workflow_id='test-workflow'
            )

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
